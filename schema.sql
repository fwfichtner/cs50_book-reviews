-- Initialize the database.
-- Drop any existing data and create empty tables.

DROP TABLE IF EXISTS users;
CREATE TABLE users (
id SERIAL PRIMARY KEY,
name VARCHAR NOT NULL,
pw VARCHAR NOT NULL
);

DROP TABLE IF EXISTS books;
CREATE TABLE books (
isbn char(10) PRIMARY KEY,
title VARCHAR,
author VARCHAR,
year integer
);

DROP TABLE IF EXISTS ureviews;
CREATE TABLE ureviews (
rev_id SERIAL,
isbn char(10) references books,
rating integer CHECK (rating < 6),
review text,
id integer REFERENCES users,
PRIMARY KEY (rev_id,isbn));

DROP TABLE IF EXISTS grreviews;
CREATE TABLE grreviews (
isbn char(10) references books,
review_count integer,
average_score decimal
);
