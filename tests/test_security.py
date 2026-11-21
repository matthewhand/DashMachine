import pytest
from flask_login import AnonymousUserMixin

from dashmachine.main.models import Groups
from dashmachine.main.utils import check_groups, safe_join


def test_security_headers_present(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "same-origin"


@pytest.mark.parametrize(
    "path",
    [
        "/tcdrop/deleteCachedFile?file=../../config.ini",
        "/tcdrop/deleteCachedFile?file=/etc/passwd",
    ],
)
def test_cached_file_path_traversal_is_refused(client, path):
    assert client.get(path).status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/settings/delete_file?folder=icons&file=../../config.ini",
        "/settings/delete_file?folder=backgrounds&file=../../../../etc/passwd",
        "/settings/delete_file?folder=elsewhere&file=x.png",
    ],
)
def test_settings_delete_traversal_is_refused(client, login, path):
    login(client)
    assert client.get(path).status_code in (400, 404)


def test_app_template_name_is_confined(client, login):
    login(client)
    assert client.get("/settings/get_app_template?name=../../config").status_code in (
        400,
        404,
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/settings/add_images"),
        ("post", "/settings/save_config"),
        ("get", "/settings/delete_file?folder=icons&file=x.png"),
        ("get", "/settings/get_app_template?name=sonarr"),
    ],
)
def test_settings_endpoints_require_admin(client, method, path):
    response = getattr(client, method)(
        path, data={"folder": "icons", "files": "", "config": ""}
    )
    assert response.status_code == 403


def test_safe_join_allows_normal_names(tmp_path):
    (tmp_path / "ok.png").write_text("x")
    assert safe_join(str(tmp_path), "ok.png").endswith("ok.png")


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../b"])
def test_safe_join_rejects_escape(tmp_path, bad):
    with pytest.raises(ValueError):
        safe_join(str(tmp_path), bad)


def test_check_groups_ignores_undefined_group(app):
    class User:
        role = "admin"
        is_anonymous = False

    with app.app_context():
        assert check_groups("ghost_group", User()) is False


def test_check_groups_matches_any_listed_role(app):
    class User:
        role = "user"
        is_anonymous = False

    with app.app_context():
        Groups.query.filter_by(name="everyone").first()  # exists from config
        assert check_groups("everyone", User()) is True


def test_anonymous_users_are_public(app):
    with app.app_context():
        user = AnonymousUserMixin()
        assert check_groups("everyone", user) is True


def test_default_admin_only_when_no_groups(app):
    class User:
        role = "admin"
        is_anonymous = False

    with app.app_context():
        assert check_groups(None, User()) is True

    class NotAdmin:
        role = "user"
        is_anonymous = False

    with app.app_context():
        assert check_groups(None, NotAdmin()) is False


def test_csrf_is_enforced_by_default(make_app):
    app = make_app(csrf=True)
    client = app.test_client()
    page = client.get("/login").get_data(as_text=True)
    assert 'name="csrf_token"' in page
    response = client.post(
        "/check_login", data={"username": "admin", "password": "test-password-1"}
    )
    assert "CSRF" in response.get_json()["data"]["err"]


def test_session_cookie_is_httponly(client, login):
    response = login(client)
    session_headers = [
        header
        for header in response.headers.getlist("Set-Cookie")
        if header.startswith("session=")
    ]
    assert session_headers
    for header in session_headers:
        assert "HttpOnly" in header
        assert "SameSite=Lax" in header
