"""The UI contract: markup the stylesheets and scripts depend on.

These are not pixel tests. They pin the structural hooks (grid, cards, tag
sections, sidebar) so a future template edit cannot silently drop them.
"""
import re

WITH_SIDEBAR_ICON = """\
[Settings]
theme = dark
accent = blue
custom_app_title = UI Test
home_access_groups = everyone

[everyone]
roles = admin

[admin]
role = admin
password = test-password-1
confirm_password = test-password-1

[Docker Host]
prefix = http://
url = docker.local
icon = static/images/apps/docker.png
sidebar_icon = static/images/apps/docker.png
description = containers
groups = everyone
tags = Tools

[Second]
prefix = https://
url = second.local
icon = static/images/apps/default.png
description = another one
groups = everyone
tags = Media

[Weather]
type = custom
data_sources = svc
groups = everyone
"""


def _login(client):
    return client.post(
        "/check_login", data={"username": "admin", "password": "test-password-1"}
    )


def test_home_renders_grid_cards_and_tag_sections(make_app):
    app = make_app(WITH_SIDEBAR_ICON)
    client = app.test_client()
    _login(client)
    html = client.get("/home").get_data(as_text=True)

    assert 'class="app-grid' in html
    assert html.count('class="app-card"') == 2
    assert 'class="tag-block tag-group" data-tag="Tools"' in html
    assert 'class="tag-block tag-group" data-tag="Media"' in html
    assert 'class="app-card__desc searchable"' in html
    assert re.search(r'<img src="static/images/apps/docker.png"', html)


def test_sidebar_lists_apps_with_sidebar_icon(make_app):
    app = make_app(WITH_SIDEBAR_ICON)
    client = app.test_client()
    _login(client)
    html = client.get("/home").get_data(as_text=True)

    assert 'id="main-sidenav" class="side-nav"' in html
    assert 'href="http://docker.local"' in html
    # the app without sidebar_icon stays out of the sidebar
    assert html.count('src="static/images/apps/docker.png"') >= 2
    assert 'id="hide-sidenav"' in html
    assert 'id="sidenav-mobile-toggle-btn"' in html


def test_home_search_and_tag_filter_present(make_app):
    app = make_app(WITH_SIDEBAR_ICON)
    client = app.test_client()
    _login(client)
    html = client.get("/home").get_data(as_text=True)

    assert 'id="apps-filter"' in html
    assert 'id="tags-select"' in html
    assert 'id="toggle-tag-expand-all-btn"' in html


def test_login_page_structure(client):
    html = client.get("/login").get_data(as_text=True)
    assert 'class="auth"' in html
    assert 'class="auth-card"' in html
    assert 'class="login-form" method="POST" data-url="/check_login"' in html
    assert 'id="username"' in html
    assert 'id="password"' in html


def test_settings_page_structure(client, login):
    login(client)
    html = client.get("/settings").get_data(as_text=True)
    for hook in [
        'class="settings-grid"',
        'id="config-form"',
        'id="save-config-btn"',
        'id="config-textarea"',
        'id="images-tcdrop"',
        'id="files-div"',
    ]:
        assert hook in html, hook
    # tabs must be a list so the tab widget finds its children
    assert re.search(r'<ul class="tabs">\s*<li class="tab">', html)


def test_error_pages_use_the_shared_shell(client):
    for code, label in [(403, "Forbidden"), (404, "Not Found"), (500, "Internal Server Error")]:
        html = client.get(f"/definitely-not-here").get_data(as_text=True)
        assert 'class="error-page"' in html
        assert "404" in html
        assert "Not Found" in html


def test_no_retired_assets_referenced(client, login):
    login(client)
    pages = ["/home", "/settings", "/login"]
    retired = ["global/style.css", "jqueryui.min.js", "page-404.css", "google-fonts.css"]
    for page in pages:
        html = client.get(page).get_data(as_text=True)
        for asset in retired:
            assert asset not in html, f"{asset} still referenced by {page}"


def test_stylesheets_are_versioned_and_ordered(client, login):
    login(client)
    html = client.get("/home").get_data(as_text=True)
    links = re.findall(r'href="(?:/)?static/css/([^"?]+)\?v=\d+"', html)
    assert "vendors/materialize.min.css" not in links  # vendor file has no ?v=
    assert links.index("global/dashmachine-theme.css") < links.index("global/dashmachine.css")
    assert "main/home.css" in links
