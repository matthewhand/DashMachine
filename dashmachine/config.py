"""Application configuration.

Values come from the environment so the same image can run anywhere, with the
previous behaviour as the default. Secrets live in the data directory, as they
always have, so existing installs keep their sessions.
"""
import os
import secrets

from dashmachine.paths import user_data_folder

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean, got {value!r}")


def load_secret_key():
    """Read the persisted secret, creating it on first boot.

    Kept in the data volume so restarting the container does not sign everyone
    out. Written with 0600 permissions.
    """
    path = os.path.join(user_data_folder, ".secret")
    try:
        with open(path, "r", encoding="utf-8") as secret_file:
            key = secret_file.read().strip()
    except FileNotFoundError:
        key = ""

    if len(key) < 32:
        key = secrets.token_hex(32)
        os.makedirs(user_data_folder, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as secret_file:
            secret_file.write(key)
    return key


class Config:
    SECRET_KEY = load_secret_key()

    # Absolute path: Flask-SQLAlchemy 3 resolves relative SQLite paths against
    # the instance folder, which is not where the data volume is mounted.
    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + os.path.join(user_data_folder, "site.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    CONTEXT_PATH = os.environ.get("CONTEXT_PATH", "").rstrip("/")

    # Revalidate static assets on every request (ETags still give 304s) so a
    # replaced icon or background shows up immediately.
    SEND_FILE_MAX_AGE_DEFAULT = 0

    # 64 MiB is far above any icon or background this app handles, and stops an
    # unauthenticated upload from filling the disk.
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable when the app is only reachable over HTTPS.
    SESSION_COOKIE_SECURE = env_bool("DASHMACHINE_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
