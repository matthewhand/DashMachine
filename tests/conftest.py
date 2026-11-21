import os
import shutil
import tempfile
from pathlib import Path

USER_DATA = Path(tempfile.mkdtemp(prefix="dashmachine-tests-"))
# paths.py reads this at import time, so it must be set before the app is
# imported anywhere in the test session.
os.environ["DASHMACHINE_USER_DATA"] = str(USER_DATA)

import pytest  # noqa: E402

from dashmachine import create_app  # noqa: E402
from dashmachine import sources as sources_module  # noqa: E402
from dashmachine.main import utils as main_utils  # noqa: E402
from dashmachine.main.utils import dashmachine_init  # noqa: E402
from dashmachine.settings_system import utils as settings_utils  # noqa: E402

PACKAGE = Path(__file__).resolve().parent.parent
BUNDLED_APPS = PACKAGE / "dashmachine" / "static" / "images" / "apps"

BASE_CONFIG = """\
[Settings]
theme = dark
accent = blue
custom_app_title = Test Dashboard
home_access_groups = everyone

[everyone]
roles = admin,user,public_user

[admin]
role = admin
password = test-password-1
confirm_password = test-password-1

[visitor]
role = user
theme = light

[svc]
platform = rest
resource = http://example.invalid/api
value_template = {{ value }}

[Example]
prefix = http://
url = example.com
icon = static/images/apps/default.png
description = an app
groups = everyone
tags = Tools, Media
data_sources = svc

[Second]
prefix = https://
url = example.org
groups = everyone

[Hidden]
prefix = https://
url = hidden.example
"""


@pytest.fixture()
def images_dir(tmp_path, monkeypatch):
    """A scratch copy of the bundled icons, with user folders alongside."""
    images = tmp_path / "images"
    shutil.copytree(BUNDLED_APPS, images / "apps")
    (images / "backgrounds").mkdir()
    (images / "icons").mkdir()
    monkeypatch.setattr(main_utils, "images_folder", str(images))
    monkeypatch.setattr(
        settings_utils, "backgrounds_images_folder", str(images / "backgrounds")
    )
    monkeypatch.setattr(settings_utils, "icons_images_folder", str(images / "icons"))
    monkeypatch.setattr(
        sources_module, "backgrounds_images_folder", str(images / "backgrounds")
    )
    return images


@pytest.fixture()
def make_app(images_dir):
    """Build an app from a config.ini string and initialise it."""

    def _make(config=BASE_CONFIG, csrf=False, keep_auth_cache=False, **overrides):
        if keep_auth_cache:
            cache = tempfile.mkdtemp(prefix="dashmachine-auth-")
            if (USER_DATA / "auth_cache").is_dir():
                shutil.copytree(USER_DATA / "auth_cache", cache, dirs_exist_ok=True)
            shutil.rmtree(USER_DATA, ignore_errors=True)
            USER_DATA.mkdir(parents=True)
            shutil.copytree(cache, USER_DATA / "auth_cache", dirs_exist_ok=True)
        else:
            shutil.rmtree(USER_DATA, ignore_errors=True)
            USER_DATA.mkdir(parents=True)
        (USER_DATA / "config.ini").write_text(config)

        app = create_app(
            TESTING=True,
            WTF_CSRF_ENABLED=csrf,
            BCRYPT_LOG_ROUNDS=4,
            **overrides,
        )
        dashmachine_init(app)
        return app

    return _make


@pytest.fixture()
def app(make_app):
    return make_app()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login():
    def _login(client, username="admin", password="test-password-1"):
        return client.post(
            "/check_login", data={"username": username, "password": password}
        )

    return _login
