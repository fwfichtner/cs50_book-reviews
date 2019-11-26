from functools import wraps
from flask import g, redirect


def login_required(f):
    """
    decorator that redirects anonymous users to the login page.
    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect("login")
        return f(*args, **kwargs)
    return decorated_function
