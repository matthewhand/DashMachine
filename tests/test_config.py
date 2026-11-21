import bcrypt
from dashmachine import db
from dashmachine.main.models import Apps, DataSources, DataSourcesArgs, Groups, Tags
from dashmachine.settings_system.models import Settings
from dashmachine.user_system.models import User

from conftest import USER_DATA


def test_settings_defaults_and_values(app):
    with app.app_context():
        settings = Settings.query.first()
        assert settings.theme == "dark"
        assert settings.accent == "blue"
        assert settings.custom_app_title == "Test Dashboard"
        assert settings.home_access_groups == "everyone"
        # settings_access_groups defaults to admin_only when unset
        assert settings.settings_access_groups == "admin_only"
        # required roles are always present
        for role in ("admin", "user", "public_user"):
            assert role in settings.roles


def test_users_hashed_and_password_blanked(app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        assert admin.role == "admin"
        assert admin.password != "test-password-1"
        assert bcrypt.checkpw(
            b"test-password-1", admin.password.encode("utf-8")
        )

    config = (USER_DATA / "config.ini").read_text()
    assert "test-password-1" not in config
    assert "password = \n" in config


def test_first_non_admin_user_is_promoted(make_app):
    config = """\
[Settings]

[someone]
role = user
password = another-password
confirm_password = another-password
"""
    app = make_app(config=config)
    with app.app_context():
        user = User.query.filter_by(username="someone").first()
        assert user.role == "admin"
    assert "role = admin" in (USER_DATA / "config.ini").read_text()


def test_password_survives_without_being_in_config(make_app):
    first = make_app()
    with first.app_context():
        original_hash = User.query.filter_by(username="admin").first().password

    config = (USER_DATA / "config.ini").read_text()
    assert "password = \n" in config

    second = make_app(config=config, keep_auth_cache=True)
    with second.app_context():
        assert User.query.filter_by(username="admin").first().password == original_hash


def test_apps_groups_tags_and_data_sources(app):
    with app.app_context():
        example = Apps.query.filter_by(name="Example").first()
        assert example.prefix == "http://"
        assert example.url == "example.com"
        assert example.groups == "everyone"
        assert example.data_sources[0].name == "svc"
        assert example.tags == "Tools, Media"

        # untagged apps get a synthetic tag
        hidden = Apps.query.filter_by(name="Hidden").first()
        assert hidden.tags == "Untagged"
        assert Tags.query.filter_by(name="Untagged").first() is not None

        ds = DataSources.query.filter_by(name="svc").first()
        args = {arg.key: arg.value for arg in ds.args}
        assert ds.platform == "rest"
        assert args["resource"] == "http://example.invalid/api"

        group = Groups.query.filter_by(name="everyone").first()
        assert "public_user" in group.roles


def test_admin_only_group_is_created(app):
    with app.app_context():
        group = Groups.query.filter_by(name="admin_only").first()
        assert group.roles == "admin"


def test_tag_icon_and_sort_position(make_app):
    config = """\
[Settings]
tags = {"name": "Tools", "icon": "build", "sort_pos": 7}

[Example]
prefix = http://
url = example.com
tags = Tools
"""
    app = make_app(config=config)
    with app.app_context():
        tag = Tags.query.filter_by(name="Tools").first()
        assert tag.icon == "build"
        assert tag.sort_pos == 7


def test_invalid_app_without_prefix(make_app):
    config = """\
[Settings]

[Broken]
url = example.com
"""
    app = make_app(config=config)
    with app.app_context():
        assert Apps.query.filter_by(name="Broken").first() is None


def test_unknown_group_is_rejected(make_app):
    config = """\
[Settings]

[Example]
prefix = http://
url = example.com
groups = nope
"""
    app = make_app(config=config)
    with app.app_context():
        assert Apps.query.filter_by(name="Example").first() is None


def test_unknown_data_source_is_rejected(make_app):
    config = """\
[Settings]

[Example]
prefix = http://
url = example.com
data_sources = missing
"""
    app = make_app(config=config)
    with app.app_context():
        assert Apps.query.filter_by(name="Example").first() is None


def test_missing_settings_section_reports_error(tmp_path):
    from dashmachine import create_app
    from dashmachine.main.read_config import read_config

    (USER_DATA / "config.ini").write_text("[Example]\nprefix = http://\n")
    app = create_app(TESTING=True, BCRYPT_LOG_ROUNDS=4)
    with app.app_context():
        db.create_all()
        result = read_config()
    assert "Settings" in result["msg"]
