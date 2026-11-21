import importlib
import logging
import os
from shutil import copyfile

from markdown2 import markdown
from PIL import Image

from dashmachine import db
from dashmachine.main.models import Groups
from dashmachine.main.read_config import read_config
from dashmachine.paths import (
    images_folder,
    root_folder,
    user_data_folder,
)
from dashmachine.version import version as dashmachine_version

log = logging.getLogger(__name__)


def row2dict(row):
    return {column.name: str(getattr(row, column.name)) for column in row.__table__.columns}


def safe_join(base, *names):
    """Join user-supplied names to *base*, refusing anything that escapes it."""
    base = os.path.realpath(base)
    path = os.path.realpath(os.path.join(base, *names))
    if os.path.commonpath([base, path]) != base:
        raise ValueError(f"path escapes {base}: {names!r}")
    return path


# establishes routes decorated w/ @public_route as accessible while not signed
# in. See login and register routes for usage
def public_route(decorated_function):
    decorated_function.is_public = True
    return decorated_function


def _database_path(app):
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    prefix = "sqlite:///"
    return uri[len(prefix):] if uri.startswith(prefix) else None


def _link_user_folder(name):
    """Expose a user-data folder under static/ so it can be served."""
    target = os.path.join(user_data_folder, name)
    link = os.path.join(images_folder, name)
    os.makedirs(target, exist_ok=True)
    if os.path.islink(link) or os.path.exists(link):
        return
    try:
        os.symlink(target, link)
    except OSError as exc:
        log.warning("could not link %s to %s: %s", link, target, exc)


def prepare_user_data():
    """Create the writable data layout and the default config on first boot."""
    os.makedirs(user_data_folder, exist_ok=True)
    _link_user_folder("backgrounds")
    _link_user_folder("icons")

    config_file = os.path.join(user_data_folder, "config.ini")
    if not os.path.exists(config_file):
        copyfile(os.path.join(root_folder, "default_config.ini"), config_file)


def dashmachine_init(app, reset_db=True):
    """Initialise the data directory and the database.

    The database is derived state: ``config.ini`` is the source of truth, so it
    is rebuilt from scratch on every boot. Runs once, before the server starts
    accepting requests (gunicorn preloads the app).
    """
    resize_template_app_images()
    prepare_user_data()

    with app.app_context():
        if reset_db:
            db_file = _database_path(app)
            if db_file:
                for suffix in ("", "-wal", "-shm"):
                    try:
                        os.remove(db_file + suffix)
                    except FileNotFoundError:
                        pass
        db.create_all()
        db.session.commit()
        read_config()
        # Do not hand a pooled SQLite connection to forked workers.
        db.session.remove()
        db.engine.dispose()


def check_groups(groups, current_user):
    """Does this user belong to one of the comma-separated *groups*?

    Tolerates being called outside a request (for example while rendering a
    data source template), where ``current_user`` is unbound.
    """
    role = None
    if getattr(current_user, "is_anonymous", True):
        role = "public_user"
        try:
            current_user.role = "public_user"
        except (AttributeError, RuntimeError):
            pass
    else:
        role = getattr(current_user, "role", None)

    if groups:
        roles_list = []
        for group in groups.split(","):
            group_db = Groups.query.filter_by(name=group.strip()).first()
            if group_db and group_db.roles:
                roles_list += [
                    role.strip() for role in group_db.roles.split(",") if role.strip()
                ]
        return role in roles_list

    return role == "admin"


def get_data_source(data_source):
    if data_source is None:
        return "unknown data source"

    data_source_args = {}
    for arg in data_source.args:
        arg = row2dict(arg)
        data_source_args[arg.get("key")] = arg.get("value")
    data_source = row2dict(data_source)
    module = importlib.import_module(f"dashmachine.platform.{data_source['platform']}")
    platform = module.Platform(data_source, **data_source_args)
    return platform.process()


def resize_template_app_images():
    """Downscale the bundled app icons to at most 64x64.

    This runs on every boot, before the app is importable, so it must never be
    able to break startup:
      * it is idempotent - an icon already at or below 64px is left alone, so
        a normal boot performs no writes at all;
      * writes are atomic - the resized image is written to a temporary file
        in the same directory and renamed over the original, so a kill in the
        middle of a save cannot leave a truncated icon behind;
      * a damaged icon is skipped and logged instead of raising, so a single
        bad file can no longer stop the whole dashboard from starting.
    """
    folder = os.path.join(images_folder, "apps")
    try:
        filenames = sorted(os.listdir(folder))
    except FileNotFoundError:
        return
    for file in filenames:
        fp = os.path.join(folder, file)
        if file.endswith(".tmp"):
            # leftover from an interrupted atomic save
            try:
                os.remove(fp)
            except OSError:
                pass
            continue
        if not os.path.isfile(fp):
            continue
        try:
            with Image.open(fp) as image:
                image.load()
                if max(image.size) <= 64:
                    continue
                image_format = image.format or Image.registered_extensions().get(
                    os.path.splitext(file)[1].lower(), "PNG"
                )
                image.thumbnail((64, 64))
                tmp_fp = fp + ".tmp"
                try:
                    image.save(tmp_fp, format=image_format)
                    os.replace(tmp_fp, fp)
                finally:
                    if os.path.exists(tmp_fp):
                        try:
                            os.remove(tmp_fp)
                        except OSError:
                            pass
        except Exception as exc:  # noqa: BLE001 - startup must not fail here
            log.warning("skipping unreadable icon %r: %s", file, exc)
            continue


def get_update_message_html():
    try:
        with open(os.path.join(user_data_folder, ".has_read_update"), "r") as has_read:
            has_read_version = has_read.read()
    except FileNotFoundError:
        has_read_version = None
    if not has_read_version or has_read_version.strip() != dashmachine_version:
        try:
            with open(
                os.path.join(root_folder, "update_message.md"), "r", encoding="utf-8"
            ) as update_message:
                md = update_message.read()
        except FileNotFoundError:
            return ""
        return markdown(
            md,
            extras=[
                "tables",
                "fenced-code-blocks",
                "break-on-newline",
                "header-ids",
                "code-friendly",
            ],
        )
    return ""


def mark_update_message_read():
    with open(os.path.join(user_data_folder, ".has_read_update"), "w") as has_read:
        has_read.write(dashmachine_version)
