"""User accounts: creation, password checks and resets."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from .db import login_key

_hasher = PasswordHasher()


class UserError(ValueError):
    pass


def new_password():
    """Readable enough to type on a phone, long enough not to be guessed."""
    return secrets.token_urlsafe(9)


def create_user(db, name, password, is_admin=False):
    name = name.strip()
    if not name:
        raise UserError("Name fehlt.")
    if db.execute("SELECT 1 FROM users WHERE login = ?", (login_key(name),)).fetchone():
        raise UserError(f"{name} gibt es schon.")
    cur = db.execute(
        "INSERT INTO users (name, login, pw_hash, is_admin) VALUES (?, ?, ?, ?)",
        (name, login_key(name), _hasher.hash(password), int(is_admin)),
    )
    db.commit()
    return cur.lastrowid


def set_password(db, user_id, password):
    db.execute(
        "UPDATE users SET pw_hash = ?, session_epoch = session_epoch + 1 WHERE id = ?",
        (_hasher.hash(password), user_id),
    )
    db.commit()


def authenticate(db, name, password):
    user = db.execute("SELECT * FROM users WHERE login = ?", (login_key(name),)).fetchone()
    if user is None:
        # same cost as a real check, so a wrong name is not faster than a wrong password
        _hasher.hash(password)
        return None
    try:
        _hasher.verify(user["pw_hash"], password)
    except VerificationError:
        return None
    return user
