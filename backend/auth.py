import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from secrets_manager import get_secret_material
from storage_paths import DATA_DIR


BASE_DIR = DATA_DIR
AUTH_DB_PATH = Path(
    os.getenv("ATLAS_AUTH_DB_PATH", str(BASE_DIR / "auth.db"))
)
SESSION_COOKIE_NAME = "atlas_session"
SESSION_TTL_SECONDS = int(
    os.getenv("ATLAS_SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7))
)
PBKDF2_ITERATIONS = 310_000
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _connect():
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        AUTH_DB_PATH,
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            workspace_id TEXT NOT NULL UNIQUE,
            workspace_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_attempts (
            attempt_key TEXT PRIMARY KEY,
            window_started REAL NOT NULL,
            attempt_count INTEGER NOT NULL,
            blocked_until REAL NOT NULL DEFAULT 0
        )
        """
    )
    connection.commit()
    return connection


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}:{digest.hex()}"


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        salt_hex, expected_hex = encoded_hash.split(":", 1)
        actual = _hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected_hex)


def _public_user(row):
    return {
        "id": row["id"],
        "email": row["email"],
        "workspace_id": row["workspace_id"],
        "workspace_name": row["workspace_name"],
        "created_at": row["created_at"],
    }


def _session_token_hash(raw_token: str) -> str:
    configured_secret = os.getenv("ATLAS_SESSION_SECRET") or os.getenv("ATLAS_SECRET_KEY")
    secret = (
        configured_secret.encode("utf-8")
        if configured_secret
        else get_secret_material()
    )
    return hmac.new(
        secret,
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def register_user(email: str, password: str, workspace_name: str):
    normalized_email = email.strip().lower()
    normalized_workspace = workspace_name.strip()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Enter a valid email address")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if len(password) > 1024:
        raise ValueError("Password is too long")
    if not normalized_workspace or len(normalized_workspace) > 100:
        raise ValueError("Workspace name must be between 1 and 100 characters")

    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid4()),
        "email": normalized_email,
        "password_hash": _hash_password(password),
        "workspace_id": str(uuid4()),
        "workspace_name": normalized_workspace,
        "created_at": now,
    }
    connection = _connect()
    try:
        connection.execute(
            """INSERT INTO users
               (id, email, password_hash, workspace_id, workspace_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user["id"],
                user["email"],
                user["password_hash"],
                user["workspace_id"],
                user["workspace_name"],
                user["created_at"],
            ),
        )
        connection.commit()
        return _public_user(user)
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with this email already exists") from exc
    finally:
        connection.close()


def authenticate_user(email: str, password: str):
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email.strip().lower(),),
        ).fetchone()
        if not row or not _verify_password(password, row["password_hash"]):
            return None
        return _public_user(row)
    finally:
        connection.close()


def check_auth_rate_limit(key: str, *, limit: int, window_seconds: int):
    """Atomically allow a bounded number of auth attempts per caller key."""
    now = datetime.now(timezone.utc).timestamp()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM auth_attempts "
            "WHERE window_started < ? AND blocked_until <= ?",
            (now - 24 * 60 * 60, now),
        )
        row = connection.execute(
            "SELECT window_started, attempt_count, blocked_until "
            "FROM auth_attempts WHERE attempt_key = ?",
            (key,),
        ).fetchone()
        if row and row["blocked_until"] > now:
            connection.commit()
            return max(1, int(row["blocked_until"] - now))

        if (
            not row
            or now - row["window_started"] >= window_seconds
            or row["blocked_until"] > 0
        ):
            connection.execute(
                "INSERT INTO auth_attempts "
                "(attempt_key, window_started, attempt_count, blocked_until) "
                "VALUES (?, ?, 1, 0) "
                "ON CONFLICT(attempt_key) DO UPDATE SET "
                "window_started = excluded.window_started, "
                "attempt_count = 1, blocked_until = 0",
                (key, now),
            )
            connection.commit()
            return 0

        count = row["attempt_count"] + 1
        blocked_until = now + window_seconds if count > limit else 0
        connection.execute(
            "UPDATE auth_attempts SET attempt_count = ?, blocked_until = ? "
            "WHERE attempt_key = ?",
            (count, blocked_until, key),
        )
        connection.commit()
        return max(1, int(blocked_until - now)) if blocked_until else 0
    finally:
        connection.close()


def clear_auth_rate_limit(key: str):
    connection = _connect()
    try:
        connection.execute("DELETE FROM auth_attempts WHERE attempt_key = ?", (key,))
        connection.commit()
    finally:
        connection.close()


def create_session(user_id: str):
    raw_token = secrets.token_urlsafe(32)
    token_hash = _session_token_hash(raw_token)
    now = datetime.now(timezone.utc)
    connection = _connect()
    try:
        connection.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (now.timestamp(),),
        )
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                token_hash,
                user_id,
                (now + timedelta(seconds=SESSION_TTL_SECONDS)).timestamp(),
                now.isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return raw_token


def get_session_user(raw_token: str | None):
    if not raw_token:
        return None
    token_hash = _session_token_hash(raw_token)
    connection = _connect()
    try:
        row = connection.execute(
            """SELECT users.* FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
            (token_hash, datetime.now(timezone.utc).timestamp()),
        ).fetchone()
        return _public_user(row) if row else None
    finally:
        connection.close()


def revoke_session(raw_token: str | None):
    if not raw_token:
        return
    token_hash = _session_token_hash(raw_token)
    connection = _connect()
    try:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,),
        )
        connection.commit()
    finally:
        connection.close()


def cookie_is_secure() -> bool:
    production = os.getenv("ATLAS_ENV", "development").lower() == "production"
    configured = os.getenv("ATLAS_COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes"}
    return production


def require_production_auth_configuration():
    if os.getenv("ATLAS_ENV", "development").lower() == "production":
        for setting in ("ATLAS_SESSION_SECRET", "ATLAS_SECRET_KEY"):
            value = os.getenv(setting, "")
            if len(value) < 32:
                raise RuntimeError(
                    f"{setting} must be set to at least 32 characters in production"
                )
        if not cookie_is_secure():
            raise RuntimeError("ATLAS_COOKIE_SECURE must be enabled in production")
        origins = [
            origin.strip()
            for origin in os.getenv("ATLAS_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ]
        if not origins or "*" in origins:
            raise RuntimeError(
                "ATLAS_ALLOWED_ORIGINS must list exact production frontend origins"
            )
        if any(not origin.startswith("https://") for origin in origins):
            raise RuntimeError(
                "Production frontend origins must use HTTPS"
            )  # Do not accept an insecure browser origin in production.
