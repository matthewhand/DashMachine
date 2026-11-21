#!/usr/bin/env python3
"""WSGI entry point: ``gunicorn --config gunicorn.conf.py wsgi:app``."""
from dashmachine import create_app
from dashmachine.main.utils import dashmachine_init

app = create_app()
dashmachine_init(app)

if __name__ == "__main__":
    app.run()
