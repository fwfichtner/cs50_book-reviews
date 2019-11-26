import json
import os
import requests

from flask import Flask, g, session, redirect, render_template, request, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from db import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def get_db():
    # Set up database
    engine = create_engine(os.getenv("DATABASE_URL"))
    g.db = scoped_session(sessionmaker(bind=engine))
    return g.db


@app.before_request
def before_request():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = (
            get_db().execute("SELECT * FROM users WHERE id = :id", {"id": user_id}).fetchone()
        )


@app.route("/")
@login_required
def index():
    """show search"""
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Clear the current session, including the stored user id."""
    session.clear()

    """Log in a registered user by adding the user id to the session."""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute("SELECT * FROM users WHERE name = :name", {"name": username}).fetchone()

        if user is None:
            error = "Incorrect username."
        elif password != user["pw"]:
            error = "Incorrect password."

        if error is None:
            # store the user id in a new session and return to the index
            session.clear()
            session["user_id"] = user["id"]
            return redirect("/")

        flash(error)
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect("/")


@app.route("/register", methods=("GET", "POST"))
def register():
    """Register a new user.
    Validates that the username is not already taken.
    """
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif (
                db.execute("SELECT id FROM users WHERE name = :name", {"name": username}).fetchone()
                is not None
        ):
            error = "User {0} is already registered.".format(username)

        if error is None:
            # the name is available, store it in the database and go to
            # the login page
            db.execute(
                "INSERT INTO users (name, pw) VALUES (:name, :pw)",
                {"name": username, "pw": password}
            )
            db.commit()
            return redirect("/login")

        flash(error)
    return render_template("register.html")


@app.route("/search", methods=["GET"])
@login_required
def search():
    """ Get books results """
    error = None

    # take book from user input
    searched_book = request.args.get("book")
    # capitalize and add wildcard for postgres
    searched_book = f"%{searched_book.title()}%"

    db = get_db()
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn LIKE :searched_book OR \
                        title LIKE :searched_book OR \
                        author LIKE :searched_book",
                      {"searched_book": searched_book})

    if rows.rowcount == 0:
        error = "Sorry, no books found with this search."

    if error is None:
        books = rows.fetchall()
        return render_template("results.html", books=books)

    flash(error)
    return redirect("/")


@app.route("/book/<string:isbn>", methods=['GET', 'POST'])
@login_required
def book(isbn):
    """ Get book information, make review"""
    db = get_db()
    error = None

    if request.method == 'GET':
        book = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                                isbn = :isbn",
                         {"isbn": isbn}).fetchall()

        reviews = db.execute("SELECT id, rating, review FROM ureviews WHERE \
                                isbn = :isbn",
                         {"isbn": isbn}).fetchall()

        # goodreads reviews via API
        r = requests.get("https://www.goodreads.com/book/review_counts.json",
                         params={"key": open(r"goodreads_apikey.txt", "r").read(), "isbns": isbn})  # TODO
        gr = r.json()
        goodreads = [gr['books'][0]['ratings_count'], gr['books'][0]['average_rating']]

        return render_template("book.html", book=book, reviews=reviews, goodreads=goodreads)

    else:
        user_id = g.user["id"]

        test = db.execute("SELECT rev_id FROM ureviews WHERE id = :user_id AND isbn = :isbn LIMIT 5",
                    {"user_id": user_id,
                     "isbn": isbn})
        if test.rowcount > 0:
            error = "Error: You already submitted a review for this book."
            flash(error)
            return redirect("/book/" + isbn)

        # take review from user input
        rating = request.form.get("rating")
        rating = int(rating)
        rev = request.form.get("rev")

        db.execute(
            "INSERT INTO ureviews (isbn, rating, review, id) VALUES (:isbn, :rating, :review, :id)",
            {"isbn": isbn, "rating": rating, "review": rev, "id": user_id}
        )
        db.commit()
        return redirect("/book/" + isbn)


@app.route("/api/<string:isbn>", methods=['GET'])
@login_required
def api(isbn):
    """
    {
    "title": "Memory",
    "author": "Doug Lloyd",
    "year": 2015,
    "isbn": "1632168146",
    "review_count": 28,
    "average_score": 5.0
    }
    """
    db = get_db()

    book = db.execute("SELECT books.isbn, books.title, books.author, books.year, \
                      COUNT(ureviews.rating) as review_count, to_char(AVG(ureviews.rating), '999D99S') as average_score \
                      FROM books \
                      INNER JOIN ureviews \
                      ON books.isbn = ureviews.isbn \
                      WHERE books.isbn = :isbn \
                      GROUP BY title, author, year, books.isbn",
                      {"isbn": isbn})
    if book.rowcount > 0:
        r = dict(book.fetchone().items())
        return json.dumps(r)  # TODO jsonify
    else:
        return "404"  # TODO jsonify


if __name__ == '__main__':
    app.run()
