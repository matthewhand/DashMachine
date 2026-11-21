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

## UI (v0.7.0)

The 2020 Materialize template theme (`global/style.css`, 4,000 lines) is gone.
It is replaced by `global/dashmachine-theme.css` (design tokens: colours, type,
radii, elevation, and the `[data-accent]` palettes `config.ini` names) and
`global/dashmachine.css` (layout, components, utilities).

- Layout is a fixed 248px sidebar plus a sticky topbar; the sidebar collapses
to a drawer under 960px. The old jQuery-UI draggable handle and the
Materialize side-nav/collapsible machinery are removed.
- The home page is a responsive CSS grid of cards (icon, name, live data-source
  output, description on hover). Tag sections became headings instead of cards.
- Settings is a two-panel layout: `config.ini` beside tabbed documentation and
  image management.
- Login and error pages are self-contained cards on a gradient background.
- Materialize remains vendored for widget behaviour only (modal, toast,
  dropdown, autocomplete, tabs); its look is overridden.
- `google-fonts.css`, `jqueryui.min.js`, `page-404.css` and the knob template
  scaffolds (`top-nav.html`, `breadcrumbs`, `register`, `add_payment_method`)
  are deleted; nothing referenced them.

Two bugs surfaced while rebuilding: the update-message modal tested
`.text().length` on a whitespace-filled div, so it opened blank on *every* page
load and blocked the sign-in form; and two icon ligatures (`grid_view`,
`logout`) do not exist in the vendored Material Icons Outlined font, so they
rendered as fallback words and forced a horizontal scrollbar.

## Tests

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest        # 127 tests
.venv/bin/python -m pytest --cov=dashmachine   # 93% statement coverage
```

`tests/test_platform_modules.py` drives every integration adapter against a
mocked API (docker, sonarr/radarr/lidarr, tautulli, healthchecks, pihole, plex,
weather, deluge, transmission, ping, curl, rest); `tests/test_internals.py`
covers config, the update message, random backgrounds and the image endpoints;
`tests/test_ui.py` pins the markup hooks the CSS and JS depend on.

The UI was additionally driven in a headless Chromium: login, search
filtering, tag collapse, card hover, sidebar hide/show, the mobile drawer,
settings tabs and a config save, with zero console errors and no horizontal
overflow at 1440px or 390px.

`.github/workflows/tests.yml` runs the same suite plus a Docker build.

## Building and deploying

```sh
docker build -t dashmachine:0.7.0 .
```

The image re-creates the `static/images/{icons,backgrounds}` symlinks to
`user_data/` at build time. The data volume must be writable by uid 1000:

```sh
chown -R 1000:1000 /opt/stacks/dashmachine/data
```

Deployed on docker1 (`10.0.0.107`) as the container `dashmachine`
(`dashmachine:0.7.0`), data at `/opt/stacks/dashmachine/data`. The previous
container is kept stopped as `dashmachine-old-0.6.0` for rollback, and the
image `dashmachine:0.6.0` is still present.

## Upstream

`git remote add upstream https://github.com/rmountjoy92/DashMachine` then
`git fetch upstream` to see if anything ever lands. If upstream revives, these
changes are separable and most are PR-able.
