"""SQLite storage: users and the countries each of them has visited."""

import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    -- login is by first name, case-insensitive
    login TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    -- bumped on a password reset, which logs out every existing session
    session_epoch INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS visits (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    country TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, country)
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_key(name):
    return name.strip().casefold()
