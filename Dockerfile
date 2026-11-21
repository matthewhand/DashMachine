# syntax=docker/dockerfile:1
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# ping backs the `ping` data source
RUN apt-get update -q \
    && apt-get install --no-install-recommends -qy iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /dashmachine

# Dependencies first: hashed, fully pinned, and cached independently of source.
COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt

COPY . .

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
    && rm -rf .git .venv .uv-cache .pytest_cache tests requirements-dev.in \
              requirements-dev.txt Dockerfile.patched screenshot*.png \
    && mkdir -p dashmachine/user_data/backgrounds dashmachine/user_data/icons \
              dashmachine/static/cache \
    && rm -rf dashmachine/static/images/backgrounds dashmachine/static/images/icons \
    && ln -s ../../user_data/backgrounds dashmachine/static/images/backgrounds \
    && ln -s ../../user_data/icons dashmachine/static/images/icons \
    && chown -R app:app /dashmachine

USER app

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:5000' + os.environ.get('CONTEXT_PATH', '') + '/api/version', timeout=3)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
