### DashMachine v0.6.0 — maintained fork

This instance now runs `matthewhand/DashMachine`, a maintained fork of the
2020 upstream. Same config.ini, same dashboard — updated runtime:

- Python 3.13, Flask 3.1, SQLAlchemy 2.1, current Pillow; every dependency
  pinned and hash-locked.
- Runs unprivileged, with a healthcheck, behind gunicorn with threaded workers.
- Template icons are only resized when needed, written atomically, and a
  damaged icon is skipped instead of stopping the app.
- Settings, image and cache-file endpoints require admin rights, and
  path-traversal attempts are rejected.
- JS and CSS are served as cacheable files instead of being minified on every
  page load.
