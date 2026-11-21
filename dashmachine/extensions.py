"""Flask extension instances.

These hold no application state until ``init_app`` is called, which keeps the
app factory testable and allows more than one app per process.
"""
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
