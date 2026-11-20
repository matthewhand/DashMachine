# DashMachine — local fork

Fork of [rmountjoy92/DashMachine](https://github.com/rmountjoy92/DashMachine)
(GPL-3.0), taken 2026-11-21 because upstream is unmaintained: last commit
2020-09-22, last image push the same day, `v0.5`, 16 open PRs.

## What this fork changes

`resize_template_app_images()` in `dashmachine/main/utils.py` is fixed. The
upstream version opens **every** bundled app icon and saves it back over
itself in place, on every boot, with no error handling:

```python
for file in os.listdir(folder):
    image = Image.open(fp)
    image.thumbnail((64, 64))
    image.save(fp)           # truncates the file in place
```

Two failure modes follow. A kill during a save leaves a truncated PNG, and
because `dashmachine_init()` runs before the app is importable, the next
`Image.open()` raises and gunicorn's worker dies — so the container
crash-loops forever on the same file. And since every boot rewrites all icons,
the window reopens on every restart, including scheduled shutdowns.

The patch makes the function:

* **idempotent** — icons already at or below 64px are skipped, so a normal
  boot writes nothing at all;
* **atomic** — the resized image is written to `*.tmp` and `os.replace()`d
  over the original, so an interrupted save cannot truncate an icon;
* **fault tolerant** — a damaged icon is logged and skipped instead of
  raising, so one bad file cannot stop the dashboard starting.

Stale `*.tmp` files from an interrupted save are cleaned up on the next boot.

## Building and deploying

`Dockerfile.patched` builds on the last published image (pinned by digest) and
overlays only the patched module, so the 2020 dependency set is untouched.
Do **not** build from the upstream `Dockerfile`: its unpinned
`requirements.txt` does not resolve on python:3.8 in 2026.

```sh
docker build -f Dockerfile.patched -t dashmachine:0.5-patched .
```

Deployed on docker1 (`10.0.0.107`) as `/opt/src/DashMachine`, with
`/opt/stacks/dashmachine/docker-compose.yml` pointed at
`dashmachine:0.5-patched`.

## Upstream

`git remote add upstream https://github.com/rmountjoy92/DashMachine` then
`git fetch upstream` to see if anything ever lands. If upstream revives, the
patch is small enough to rebase or send as a PR.
