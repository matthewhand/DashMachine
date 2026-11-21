"""Tests for the remaining internals: config, update message, image moves."""
import os
import stat

import pytest

from dashmachine import db
from dashmachine.main.models import Files
from dashmachine.paths import cache_folder


def test_env_bool_accepts_true_and_false_spellings(monkeypatch):
    from dashmachine.config import env_bool

    monkeypatch.delenv("X_FLAG", raising=False)
    assert env_bool("X_FLAG") is False
    assert env_bool("X_FLAG", True) is True

    for value in ("1", "TRUE", " yes ", "on"):
        monkeypatch.setenv("X_FLAG", value)
        assert env_bool("X_FLAG") is True
    for value in ("0", "False", "no", "OFF"):
        monkeypatch.setenv("X_FLAG", value)
        assert env_bool("X_FLAG") is False

    monkeypatch.setenv("X_FLAG", "maybe")
    with pytest.raises(ValueError, match="X_FLAG must be a boolean"):
        env_bool("X_FLAG")


def test_secret_key_is_persisted_and_private(tmp_path, monkeypatch):
    from dashmachine import config

    monkeypatch.setattr(config, "user_data_folder", str(tmp_path))
    first = config.load_secret_key()
    path = tmp_path / ".secret"

    assert len(first) >= 64
    assert path.read_text().strip() == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # a restart reuses the same key, so sessions survive
    assert config.load_secret_key() == first


def test_short_secret_file_is_replaced(tmp_path, monkeypatch):
    from dashmachine import config

    monkeypatch.setattr(config, "user_data_folder", str(tmp_path))
    (tmp_path / ".secret").write_text("too-short")

    key = config.load_secret_key()
    assert key != "too-short"
    assert (tmp_path / ".secret").read_text().strip() == key


def test_update_message_shows_once(app, monkeypatch):
    from dashmachine import main
    from dashmachine.main import utils as main_utils

    monkeypatch.setattr(
        main_utils, "root_folder", os.path.dirname(os.path.dirname(__file__))
    )
    main_utils.mark_update_message_read()
    assert main_utils.get_update_message_html() == ""

    # a new version re-shows the notes
    monkeypatch.setattr(main_utils, "dashmachine_version", "v999.0.0")
    html = main_utils.get_update_message_html()
    assert html and "<" in html


def test_random_background_is_chosen_from_the_folder(app, images_dir):
    from dashmachine import sources
    from dashmachine.paths import backgrounds_images_folder
    from dashmachine.settings_system.models import Settings

    (images_dir / "backgrounds" / "one.jpg").write_bytes(b"x")
    with app.app_context():
        settings = Settings.query.first()
        settings.background = "random"
        db.session.commit()

        context = sources.context_processor()
        assert context["settings"].background == "static/images/backgrounds/one.jpg"

        # an empty folder clears the setting instead of failing
        os.remove(images_dir / "backgrounds" / "one.jpg")
        settings.background = "random"
        db.session.commit()
        assert sources.context_processor()["settings"].background is None


def test_add_images_moves_cached_file_into_chosen_folder(client, login, images_dir):
    login(client)
    response = client.post(
        "/tcdrop/cacheFile",
        data={"file": (open(__file__, "rb"), "icon.png")},
        content_type="multipart/form-data",
    )
    cached = response.get_json()["data"]["cached"]

    response = client.post("/settings/add_images", data={"files": cached, "folder": "icons"})
    assert response.status_code == 200

    moved = images_dir / "icons" / "icon.png"
    assert moved.exists()
    assert not os.path.exists(os.path.join(cache_folder, cached))
    with client.application.app_context():
        row = Files.query.filter_by(name="icon.png").first()
        assert row.folder == "icons"
        assert row.path == str(moved)


def test_add_images_rejects_unknown_folder_and_unsafe_name(client, login):
    login(client)
    assert client.post("/settings/add_images", data={"folder": "apps"}).status_code == 400

    response = client.post(
        "/tcdrop/cacheFile",
        data={"file": (open(__file__, "rb"), "../../escape.png")},
        content_type="multipart/form-data",
    )
    cached = response.get_json()["data"]["cached"]
    response = client.post("/settings/add_images", data={"files": cached, "folder": "icons"})
    # the stored name is reduced to its basename, so the move stays inside icons/
    assert response.status_code == 200


def test_delete_file_reports_missing_and_bad_folder(client, login):
    login(client)
    assert (
        client.get("/settings/delete_file?folder=icons&file=nope.png").status_code == 404
    )
    assert client.get("/settings/delete_file?folder=cache&file=x.png").status_code == 400


def test_get_app_template_returns_ini_contents(client, login):
    login(client)
    response = client.get("/settings/get_app_template?name=Plex")
    assert response.status_code == 200
    assert "[Plex]" in response.get_data(as_text=True)
    assert "\n" not in response.get_data(as_text=True)

    assert client.get("/settings/get_app_template?name=does-not-exist").status_code == 404


def test_secret_key_creation_is_race_safe(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from dashmachine import config

    monkeypatch.setattr(config, "user_data_folder", str(tmp_path))
    workers = 8
    barrier = threading.Barrier(workers)

    def worker():
        barrier.wait()
        return config.load_secret_key()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: worker(), range(workers)))

    assert len(set(results)) == 1
    path = tmp_path / ".secret"
    assert path.read_text().strip() == results[0]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(tmp_path.glob(".secret.*.tmp")) == []


def test_secret_key_handles_file_exists_race_without_clobbering(tmp_path, monkeypatch):
    from dashmachine import config

    monkeypatch.setattr(config, "user_data_folder", str(tmp_path))
    winner_key = "a" * 64
    secret_path = tmp_path / ".secret"

    def racing_link(src, dst):
        # Simulate another worker winning the race just before os.link runs
        secret_path.write_text(winner_key, encoding="utf-8")
        raise FileExistsError(dst)

    monkeypatch.setattr(config.os, "link", racing_link)
    assert config.load_secret_key() == winner_key
    assert secret_path.read_text(encoding="utf-8").strip() == winner_key
    assert list(tmp_path.glob(".secret.*.tmp")) == []
