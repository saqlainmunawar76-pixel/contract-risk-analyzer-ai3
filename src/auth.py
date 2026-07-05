"""
auth.py
=======
Authentication layer: registration, login, session helpers, role checks.

Security notes:
    - Passwords are hashed with bcrypt (salt generated per-password, cost
      factor 12). Plaintext passwords are never stored or logged.
    - Basic input validation (email format, username rules, password
      strength) happens here so bad data never reaches storage.py.
    - The first user ever registered on a fresh DB is automatically made
      'admin' so there's always at least one admin account without needing
      to hand-edit the database.
"""

import re
import bcrypt
from src import storage

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Raised for any user-facing authentication/registration problem."""
    pass


def _validate_password_strength(password: str):
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise AuthError("Password must contain both letters and numbers.")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def register_user(username: str, email: str, password: str, confirm_password: str) -> dict:
    """Validate + create a new user. Returns the created user dict (no password hash)."""
    username = username.strip()
    email = email.strip().lower()

    if not USERNAME_RE.match(username):
        raise AuthError("Username must be 3-20 characters: letters, numbers, underscore only.")
    if not EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    if password != confirm_password:
        raise AuthError("Passwords do not match.")
    _validate_password_strength(password)

    if storage.get_user_by_username(username):
        raise AuthError("That username is already taken.")
    if storage.get_user_by_email(email):
        raise AuthError("An account with that email already exists.")

    # First user on a fresh install becomes admin automatically.
    is_first_user = len(storage.list_all_users()) == 0
    role = "admin" if is_first_user else "user"

    pw_hash = hash_password(password)
    storage.create_user(username, email, pw_hash, role=role)
    user = storage.get_user_by_username(username)
    storage.log_action(user["id"], username, "register", f"role={role}")
    return _public_user(user)


def login_user(username: str, password: str) -> dict:
    """Validate credentials. Returns public user dict on success, raises AuthError on failure."""
    username = username.strip()
    user = storage.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        # Same error for unknown-user and wrong-password so we don't leak which one it was.
        raise AuthError("Invalid username or password.")

    storage.update_last_login(user["id"])
    storage.log_action(user["id"], user["username"], "login")
    return _public_user(user)


def logout_user(user_id: int, username: str):
    storage.log_action(user_id, username, "logout")


def is_admin(user: dict) -> bool:
    return bool(user) and user.get("role") == "admin"


def _public_user(user: dict) -> dict:
    """Strip sensitive fields before handing the user dict to session_state/UI."""
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
    }
