from flask_login import UserMixin

from dashmachine import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String())
    theme = db.Column(db.String())
    background = db.Column(db.String())
    accent = db.Column(db.String())
    sidebar_default = db.Column(db.String())
    tags_expanded = db.Column(db.String())
