"""DashMachine — a bookmark dashboard.

Build an app with :func:`dashmachine.create_app`; the extension objects are
re-exported for convenience.
"""
from dashmachine.app import create_app
from dashmachine.extensions import bcrypt, db, login_manager

__all__ = ["create_app", "db", "bcrypt", "login_manager"]
