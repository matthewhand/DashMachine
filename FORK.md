# DashMachine — maintained fork

Fork of [rmountjoy92/DashMachine](https://github.com/rmountjoy92/DashMachine)
(GPL-3.0), taken 2026-11-21 because upstream is dormant: last commit
2020-09-22, last image push the same day, `v0.5`, 16 open PRs.

This fork keeps the app's behaviour and `config.ini` format and replaces the
2020 runtime with a supported one.

## What changed

**Runtime.** Python 3.8 → 3.13; Flask 1.x → 3.1; Flask-SQLAlchemy 3.1 on
SQLAlchemy 2.1; current Pillow, Werkzeug, WTForms, requests. Every dependency
is declared in `requirements.in` and resolved into a hash-locked
`requirements.txt` (installed with `--require-hashes`), so a rebuild is
reproducible and cannot drift.

**Structure.** `create_app()` in `dashmachine/app.py` replaces the
import-time `Flask()` singleton; extensions live in `dashmachine/extensions.py`
and settings in `dashmachine/config.py` (all overridable by env: `CONTEXT_PATH`,
`DASHMACHINE_USER_DATA`, `DASHMACHINE_COOKIE_SECURE`, `LISTEN`, `WEB_WORKERS`).

**Boot safety.** `resize_template_app_images()` is idempotent (icons at or
below 64px are skipped, so a normal boot writes nothing), atomic (write to
`*.tmp`, `os.replace()`), and fault tolerant (a damaged icon is logged and
skipped instead of killing the worker). This is the crash loop that started
the fork: upstream rewrote all 87 icons in place on every boot, so a kill
mid-save left a truncated PNG and the container looped forever.

**Removed dead weight.** Flask-RESTful (one endpoint, now a plain route),
Flask-Caching (never used), Flask-Script (never used), Alembic (migrations
directory was unused; the DB is rebuilt from `config.ini` on every boot),
jsmin/htmlmin/cssmin (assets are served as cacheable static files with a
mtime-based `?v=` query instead of being minified per request).

**Security and correctness.**
- `/settings/*`, image upload/delete and the app-template endpoint now require
  `settings_access_groups` membership (previously any visitor could POST a new
  `config.ini`).
- Path traversal in `/tcdrop/deleteCachedFile`, `/settings/delete_file` and
  `/settings/get_app_template` is rejected.
- `/app_view?<id>` actually resolves (the old rule was `/app_view?<app_id>`,
  which matched no request, so the wrapper page always 404'd).
- Unknown ids return 404 instead of a 500, undefined groups no longer raise,
  and every platform HTTP call has a timeout.
- `X-Content-Type-Options`, `X-Frame-Options` and `Referrer-Policy` on every
  response; session cookies are `HttpOnly` + `SameSite=Lax`.

**Container.** `python:3.13-slim`, non-root uid 1000, hashed dependency
install, healthcheck on `/api/version`, gunicorn with `gthread` workers and
`preload_app` so the one-off DB rebuild happens once in the master; each
worker disposes the inherited SQLite connection in `post_fork`.

## Tests

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest        # 61 tests
```

`.github/workflows/tests.yml` runs the same suite plus a Docker build.

## Building and deploying

```sh
docker build -t dashmachine:0.6.0 .
```

The image re-creates the `static/images/{icons,backgrounds}` symlinks to
`user_data/` at build time. The data volume must be writable by uid 1000:

```sh
chown -R 1000:1000 /opt/stacks/dashmachine/data
```

Deployed on docker1 (`10.0.0.107`): source at `/opt/src/DashMachine`,
`/opt/stacks/dashmachine/docker-compose.yml` pinned to the built image with
`pull_policy: never`.

## Upstream

`git remote add upstream https://github.com/rmountjoy92/DashMachine` then
`git fetch upstream` to see if anything ever lands. If upstream revives, these
changes are separable and most are PR-able.
