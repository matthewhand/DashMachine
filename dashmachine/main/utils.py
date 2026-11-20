import os
import importlib
from shutil import copyfile
from PIL import Image
from markdown2 import markdown
from dashmachine.paths import (
    dashmachine_folder,
    images_folder,
    root_folder,
    user_data_folder,
)
from dashmachine.main.models import Groups
from dashmachine.main.read_config import read_config
from dashmachine.version import version as dashmachine_version
from dashmachine import db


def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = str(getattr(row, column.name))

    return d


# establishes routes decorated w/ @public_route as accessible while not signed
# in. See login and register routes for usage
def public_route(decorated_function):
    decorated_function.is_public = True
    return decorated_function


def dashmachine_init():
    resize_template_app_images()
    db.create_all()
    db.session.commit()

    user_data_folder = os.path.join(dashmachine_folder, "user_data")

    # create the user_data subdirectories, link them to static
    user_backgrounds_folder = os.path.join(user_data_folder, "backgrounds")
    backgrounds_folder = os.path.join(images_folder, "backgrounds")
    if not os.path.isdir(user_backgrounds_folder):
        os.mkdir(user_backgrounds_folder)
    if not os.path.isdir(backgrounds_folder):
        os.symlink(user_backgrounds_folder, backgrounds_folder)

    user_icons_folder = os.path.join(user_data_folder, "icons")
    icons_folder = os.path.join(images_folder, "icons")
    if not os.path.isdir(user_icons_folder):
        os.mkdir(user_icons_folder)
    if not os.path.isdir(icons_folder):
        os.symlink(user_icons_folder, icons_folder)

    config_file = os.path.join(user_data_folder, "config.ini")
    if not os.path.exists(config_file):
        copyfile("default_config.ini", config_file)

    read_config()


def check_groups(groups, current_user):
    if current_user.is_anonymous:
        current_user.role = "public_user"

    if groups:
        groups_list = groups.split(",")
        roles_list = []
        for group in groups_list:
            group = Groups.query.filter_by(name=group.strip()).first()
            for group_role in group.roles.split(","):
                roles_list.append(group_role.strip())
        if current_user.role in roles_list:
            return True
        else:
            return False
    else:
        if current_user.role == "admin":
            return True
        else:
            return False


def get_data_source(data_source):
    data_source_args = {}
    for arg in data_source.args:
        arg = row2dict(arg)
        data_source_args[arg.get("key")] = arg.get("value")
    data_source = row2dict(data_source)
    module = importlib.import_module(
        f"dashmachine.platform.{data_source['platform']}", "."
    )
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
            print(f"dashmachine: skipping unreadable icon {file!r}: {exc}", flush=True)
            continue



def get_update_message_html():
    try:
        with open(os.path.join(user_data_folder, ".has_read_update"), "r") as has_read:
            has_read_version = has_read.read()
    except FileNotFoundError:
        has_read_version = None
    if not has_read_version or has_read_version.strip() != dashmachine_version:
        with open(
            os.path.join(root_folder, "update_message.md"), "r"
        ) as update_message:
            md = update_message.read()

        config_html = markdown(
            md,
            extras=[
                "tables",
                "fenced-code-blocks",
                "break-on-newline",
                "header-ids",
                "code-friendly",
            ],
        )
        return config_html
    else:
        return ""


def mark_update_message_read():
    with open(os.path.join(user_data_folder, ".has_read_update"), "w") as has_read:
        has_read.write(dashmachine_version)
