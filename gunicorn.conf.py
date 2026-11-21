"""Gunicorn configuration.

The app is preloaded so the one-off boot work (database rebuild from
config.ini, icon check) happens once in the master rather than racing between
workers. Each worker then discards the inherited SQLite connection so no
connection is ever shared across a fork.
"""
import multiprocessing
import os

bind = os.environ.get("LISTEN", "0.0.0.0:5000")
workers = int(os.environ.get("WEB_WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get("WEB_THREADS", 4))
worker_class = "gthread"

timeout = int(os.environ.get("WEB_TIMEOUT", 60))
graceful_timeout = 25
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
forwarded_allow_ips = "*"

preload_app = True


def post_fork(server, worker):
    from dashmachine.extensions import db
    from wsgi import app

    with app.app_context():
        db.engine.dispose()
