"""
Lightweight, self-contained authentication (no external identity provider
required). Passwords are salted and hashed with PBKDF2-HMAC-SHA256.
"""

import hashlib
import os
import secrets

from storage.database import get_connection, init_db

_ITERATIONS = 260_000


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()


def _create_user(username, password, role="user"):
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, role),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def ensure_default_admin():
    """
    Creates a default admin account on first run so there's always a way in.
    Credentials: admin / admin123 — change this after first login.
    """
    init_db()
    conn = get_connection()
    row = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
    conn.close()
    if row is None:
        _create_user("admin", "admin123", role="admin")


def register_user(username, password):
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    success = _create_user(username, password, role="user")
    if not success:
        return False, "Username already exists."
    return True, "Account created successfully."


def verify_login(username, password):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, salt, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    computed = _hash_password(password, row["salt"])
    if secrets.compare_digest(computed, row["password_hash"]):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def list_users():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
