import json
import os
from configparser import ConfigParser

from dashmachine import db
from dashmachine.main.models import Apps, DataSources, DataSourcesArgs, Groups, Tags
from dashmachine.paths import user_data_folder
from dashmachine.settings_system.models import Settings
from dashmachine.user_system.models import User
from dashmachine.user_system.utils import (
    clean_auth_cache,
    get_cached_password,
    hash_and_cache_password,
)


def row2dict(row):
    return {column.name: str(getattr(row, column.name)) for column in row.__table__.columns}


def _write_config(config):
    with open(os.path.join(user_data_folder, "config.ini"), "w") as config_file:
        config.write(config_file)


def read_config():
    """Rebuild the database from config.ini.

    config.ini is the source of truth; the database holds a parsed copy so the
    templates can query it. Returns ``{"msg": ...}`` so the settings page can
    show validation errors without raising.
    """
    config = ConfigParser(interpolation=None)
    try:
        with open(os.path.join(user_data_folder, "config.ini"), "r") as config_file:
            config.read_file(config_file)
    except Exception as exc:  # noqa: BLE001 - reported to the user
        return {"msg": f"Invalid Config: {exc}."}

    if "Settings" not in config:
        return {"msg": "Invalid Config: a [Settings] section is required."}

    ds_list = DataSources.query.all()
    for ds in ds_list:
        ds.apps.clear()
    DataSources.query.delete()
    DataSourcesArgs.query.delete()
    Apps.query.delete()
    Settings.query.delete()
    Groups.query.delete()
    Tags.query.delete()
    User.query.delete()
    db.session.commit()

    settings = None
    for section in config.sections():
        options = config[section]

        # Settings creation
        if section == "Settings":
            settings = Settings()
            settings.theme = options.get("theme", "light")
            settings.accent = options.get("accent", "orange")
            settings.background = options.get("background", "None")

            roles = options.get("roles", "admin,user,public_user")
            for required in ("admin", "user", "public_user"):
                if required not in roles:
                    roles += f",{required}"
            settings.roles = roles

            settings.home_access_groups = options.get(
                "home_access_groups", "admin_only"
            )
            settings.settings_access_groups = options.get(
                "settings_access_groups", "admin_only"
            )
            settings.custom_app_title = options.get("custom_app_title", "DashMachine")
            settings.sidebar_default = options.get("sidebar_default", "open")
            settings.tags_expanded = options.get("tags_expanded", "True")
            db.session.add(settings)
            db.session.commit()

        # User creation
        elif "role" in options:
            user = User()
            user.username = section
            user.role = options["role"]
            user.sidebar_default = options.get("sidebar_default", None)
            user.theme = options.get("theme", None)
            user.accent = options.get("accent", None)
            user.tags_expanded = options.get("tags_expanded", None)
            user.password = ""
            if not User.query.filter_by(role="admin").first() and user.role != "admin":
                print(
                    f"Invalid Config: admin user not specified, or not specified first. "
                    f"{user.username} role set to admin",
                    flush=True,
                )
                user.role = "admin"
                config.set(section, "role", "admin")
                _write_config(config)
            db.session.add(user)
            db.session.commit()

            new_password = options.get("password", None)
            if new_password:
                if new_password == options.get("confirm_password", None):
                    user.password = hash_and_cache_password(new_password, user.id)
                    db.session.merge(user)
                    db.session.commit()
            else:
                user.password = get_cached_password(user.id)
                db.session.merge(user)
                db.session.commit()

            config.set(section, "password", "")
            config.set(section, "confirm_password", "")
            _write_config(config)

        # Groups creation
        elif "roles" in options:
            group = Groups()
            group.name = section
            group.roles = options["roles"]
            db.session.add(group)
            db.session.commit()

        # Data source creation
        elif "platform" in options:
            data_source = DataSources()
            data_source.name = section
            data_source.platform = options["platform"]
            db.session.add(data_source)
            for key, value in options.items():
                if key not in ("name", "platform"):
                    db.session.add(
                        DataSourcesArgs(key=key, value=value, data_source=data_source)
                    )
            db.session.commit()

        else:
            # App creation
            app = Apps()
            app.name = section
            app.type = options.get("type", "app")

            app.prefix = options.get("prefix", None)
            if app.type == "app" and not app.prefix:
                return {"msg": f"Invalid Config: {section} does not contain prefix."}

            app.url = options.get("url", None)
            if app.type == "app" and not app.url:
                return {"msg": f"Invalid Config: {section} does not contain url."}

            app.icon = options.get("icon", None)
            app.sidebar_icon = options.get("sidebar_icon", None)
            app.description = options.get("description", None)
            app.open_in = options.get("open_in", "this_tab")
            app.urls = options.get("urls", None)

            # Validate references before the app is written, so a bad section
            # cannot leave a half-built app behind.
            if "groups" in options:
                for group_name in options["groups"].split(","):
                    if not Groups.query.filter_by(name=group_name.strip()).first():
                        return {
                            "msg": f"Invalid Config: {section} contains at group that is not defined."
                        }
                app.groups = options["groups"]
            else:
                app.groups = None

            if "data_sources" in options:
                for config_ds in options["data_sources"].split(","):
                    if not DataSources.query.filter_by(name=config_ds.strip()).first():
                        return {
                            "msg": f"Invalid Config: {section} has a data_source variable that doesn't exist."
                        }

            # Tags creation
            if "tags" in options:
                app.tags = options["tags"]
                for tag in app.tags.split(","):
                    tag = tag.strip()
                    if tag and not Tags.query.filter_by(name=tag).first():
                        tag_db = Tags(name=tag)
                        db.session.add(tag_db)
                        db.session.commit()
                        tag_db.sort_pos = tag_db.id
                        db.session.merge(tag_db)
                        db.session.commit()
            else:
                app.tags = "Untagged"
                if not Tags.query.filter_by(name="Untagged").first():
                    db.session.add(Tags(name="Untagged"))

            db.session.add(app)
            db.session.commit()

            if "data_sources" in options:
                for config_ds in options["data_sources"].split(","):
                    db_ds = DataSources.query.filter_by(name=config_ds.strip()).first()
                    if db_ds:
                        app.data_sources.append(db_ds)
                db.session.merge(app)
                db.session.commit()

    if not Groups.query.filter_by(name="admin_only").first():
        db.session.add(Groups(name="admin_only", roles="admin"))
        db.session.commit()

    tags_settings = config["Settings"].get("tags", None)
    if tags_settings:
        for tag_setting in tags_settings.replace("},{", "}%,%{").split("%,%"):
            try:
                tag_json = json.loads(tag_setting)
            except ValueError:
                continue
            tag = Tags.query.filter_by(name=tag_json.get("name", None)).first()
            if not tag:
                continue
            if tag_json.get("icon"):
                tag.icon = tag_json["icon"]
            if tag_json.get("sort_pos") is not None:
                try:
                    tag.sort_pos = int(tag_json["sort_pos"])
                except (TypeError, ValueError):
                    pass
            db.session.merge(tag)
            db.session.commit()

    clean_auth_cache()
    if not User.query.first():
        user = User(username="admin", role="admin", password="")
        db.session.add(user)
        db.session.commit()
        user.password = hash_and_cache_password("admin", user.id)
        db.session.merge(user)
        db.session.commit()

    return {
        "msg": "success",
        "settings": row2dict(settings) if settings is not None else {},
    }
