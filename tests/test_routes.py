import os

from dashmachine import db
from dashmachine.main.models import Files
from dashmachine.paths import cache_folder
from dashmachine.version import version

from conftest import BASE_CONFIG, USER_DATA


def test_api_version(client):
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.get_json() == {"Version": version}


def test_public_pages_render(client):
    assert client.get("/login").status_code == 200
    assert client.get("/unauthorized").status_code == 200
    assert client.get("/does-not-exist").status_code == 404


def test_login_rejects_bad_password(client, login):
    response = login(client, password="wrong")
    assert response.get_json()["data"]["err"] == "Password is wrong"


def test_login_rejects_unknown_user(client, login):
    response = login(client, username="nobody")
    assert response.get_json()["data"]["err"] == "User not found"


def test_login_then_logout(client, login):
    response = login(client)
    assert response.get_json()["data"]["url"] == "/home"


def test_home_allows_everyone_group(client):
    html = client.get("/home").get_data(as_text=True)
    assert "Example" in html
    assert "Test Dashboard" in html


def test_home_redirects_when_admin_only(make_app):
    config = BASE_CONFIG.replace(
        "home_access_groups = everyone", "home_access_groups = admin_only"
    )
    app = make_app(config=config)
    client = app.test_client()
    response = client.get("/home")
    assert response.status_code == 302
    assert "/unauthorized" in response.headers["Location"]


def test_app_view_renders_and_404s(client):
    with client.application.app_context():
        from dashmachine.main.models import Apps

        app_id = Apps.query.filter_by(name="Example").first().id
    assert client.get(f"/app_view?{app_id}").status_code == 200
    assert client.get("/app_view?99999").status_code == 404
    assert client.get("/app_view?not-an-id").status_code == 404


def test_data_source_endpoint(client):
    with client.application.app_context():
        from dashmachine.main.models import DataSources

        ds_id = DataSources.query.filter_by(name="svc").first().id
    assert client.get(f"/load_data_source?id={ds_id}").status_code == 200
    assert client.get("/load_data_source?id=99999").status_code == 404
    assert client.get("/load_data_source").status_code == 404


def test_settings_requires_admin(client, login):
    assert client.get("/settings").status_code == 302
    login(client)
    assert client.get("/settings").status_code == 200


def test_settings_page_shows_config(client, login):
    login(client)
    html = client.get("/settings").get_data(as_text=True)
    assert "platform = rest" in html
    assert "save_config" in html


def test_save_config_requires_admin(client):
    response = client.post("/settings/save_config", data={"config": "[Settings]"})
    assert response.status_code == 403


def test_save_config_writes_and_reloads(client, login):
    login(client)
    new_config = BASE_CONFIG + "\n[Added]\nprefix = http://\nurl = added.example\n"
    response = client.post("/settings/save_config", data={"config": new_config})
    assert response.status_code == 200
    assert response.get_json()["data"]["msg"] == "success"
    assert "[Added]" in (USER_DATA / "config.ini").read_text()

    from dashmachine.main.models import Apps

    with client.application.app_context():
        assert Apps.query.filter_by(name="Added").first() is not None


def test_save_config_reports_invalid_config(client, login):
    login(client)
    response = client.post(
        "/settings/save_config", data={"config": "[Settings]\n[Bad]\nurl = x\n"}
    )
    assert response.get_json()["data"]["msg"].startswith("Invalid Config")


def test_image_upload_and_cache_clear(client, login):
    login(client)
    response = client.post(
        "/tcdrop/cacheFile",
        data={"file": (open(__file__, "rb"), "picture.png")},
        content_type="multipart/form-data",
    )
    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["cached"].endswith(".png")
    cached_path = os.path.join(cache_folder, payload["cached"])
    assert os.path.exists(cached_path)

    with client.application.app_context():
        assert Files.query.filter_by(cache=payload["cached"]).first() is not None

    assert client.get("/tcdrop/clearCache").data == b"success"
    assert not os.path.exists(cached_path)


def test_delete_cached_file(client, login):
    login(client)
    response = client.post(
        "/tcdrop/cacheFile",
        data={"file": (open(__file__, "rb"), "note.txt")},
        content_type="multipart/form-data",
    )
    cached = response.get_json()["data"]["cached"]
    assert client.get(f"/tcdrop/deleteCachedFile?file={cached}").data == b"success"
    assert not os.path.exists(os.path.join(cache_folder, cached))


def test_upload_requires_a_file(client):
    assert client.post("/tcdrop/cacheFile", data={}).status_code == 400


def test_unsafe_extension_is_neutralised(client):
    response = client.post(
        "/tcdrop/cacheFile",
        data={"file": (open(__file__, "rb"), "evil.sh.exe?x=1")},
        content_type="multipart/form-data",
    )
    assert response.get_json()["data"]["cached"].endswith(".bin")
