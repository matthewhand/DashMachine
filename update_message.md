### DashMachine v0.7.0 — new interface

The dashboard has been rebuilt on a modern design system instead of the 2020
Materialize template:

- A proper sidebar and topbar; the sidebar collapses to a drawer on phones.
- Cards are a responsive grid with the icon, name, live data and a description
  on hover; tags are section headings instead of cards.
- Settings is two panels: `config.ini` on the left, documentation and image
  management on the right.
- Light and dark themes, and every accent colour in `config.ini`, restyled.
- The update notice no longer blocks the sign-in screen, and the page no longer
  scrolls sideways.

Your `config.ini`, cards, icons and login are unchanged.

---

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
