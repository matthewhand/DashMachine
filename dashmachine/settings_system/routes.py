import os
from configparser import ConfigParser
from shutil import move

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from wtforms.fields.choices import SelectChoice

from dashmachine import db
from dashmachine.main.models import Files
from dashmachine.main.read_config import read_config
from dashmachine.main.utils import check_groups, safe_join
from dashmachine.paths import (
    backgrounds_images_folder,
    icons_images_folder,
    template_apps_folder,
    user_data_folder,
)
from dashmachine.settings_system.forms import ConfigForm
from dashmachine.settings_system.models import Settings
from dashmachine.settings_system.utils import get_config_html, load_files_html
from dashmachine.user_system.forms import UserForm
from dashmachine.user_system.models import User
from dashmachine.version import revision_number, version

settings_system = Blueprint("settings_system", __name__)

IMAGE_FOLDERS = {
    "icons": icons_images_folder,
    "backgrounds": backgrounds_images_folder,
}


def _can_edit_settings():
    settings_db = Settings.query.first()
    if settings_db is None:
        return False
    return check_groups(settings_db.settings_access_groups, current_user)


@settings_system.route("/settings", methods=["GET"])
def settings():
    settings_db = Settings.query.first()
    if settings_db is None:
        abort(404)
    if not _can_edit_settings():
        return redirect(url_for("main.home"))

    config_form = ConfigForm()
    user_form = UserForm()
    user_form.role.choices += [
        SelectChoice(role, role) for role in settings_db.roles.split(",")
    ]
    with open(os.path.join(user_data_folder, "config.ini"), "r") as config_file:
        config_form.config.data = config_file.read()
    files_html = load_files_html()

    template_apps = []
    for template_app_ini in sorted(os.listdir(template_apps_folder)):
        config = ConfigParser(interpolation=None)
        config.read(os.path.join(template_apps_folder, template_app_ini))
        section = template_app_ini.replace(".ini", "")
        if section in config:
            template_apps.append(f"{section}&&{config[section].get('icon', '')}")

    return render_template(
        "settings_system/settings.html",
        config_form=config_form,
        files_html=files_html,
        user_form=user_form,
        template_apps=",".join(template_apps),
        version=version,
        revision_number=revision_number,
        users=User.query.all(),
        config_readme=get_config_html(),
    )


@settings_system.route("/settings/save_config", methods=["POST"])
def save_config():
    if not _can_edit_settings():
        abort(403)
    with open(os.path.join(user_data_folder, "config.ini"), "w") as config_file:
        config_file.write(request.form.get("config", ""))
    return jsonify(data=read_config())


@settings_system.route("/settings/add_images", methods=["POST"])
def add_images():
    if not _can_edit_settings():
        abort(403)
    folder = request.form.get("folder")
    if folder not in IMAGE_FOLDERS:
        abort(400)

    for cached_file in request.form.get("files", "").split(","):
        if not cached_file:
            continue
        file = Files.query.filter_by(cache=cached_file).first()
        if file is None:
            continue
        try:
            new_path = safe_join(IMAGE_FOLDERS[folder], os.path.basename(file.name))
        except ValueError:
            abort(400)
        move(file.path, new_path)
        file.folder = folder
        file.path = new_path
        db.session.merge(file)
    db.session.commit()
    return load_files_html()


@settings_system.route("/settings/delete_file", methods=["GET"])
def delete_file():
    if not _can_edit_settings():
        abort(403)
    folder = request.args.get("folder")
    if folder not in IMAGE_FOLDERS:
        abort(400)
    try:
        file = safe_join(IMAGE_FOLDERS[folder], os.path.basename(request.args.get("file", "")))
    except ValueError:
        abort(400)
    try:
        os.remove(file)
    except FileNotFoundError:
        abort(404)
    return load_files_html()


@settings_system.route("/settings/get_app_template", methods=["GET"])
def get_app_template():
    if not _can_edit_settings():
        abort(403)
    name = os.path.basename(request.args.get("name", "")).replace(".ini", "")
    try:
        fn = safe_join(template_apps_folder, f"{name}.ini")
    except ValueError:
        abort(400)
    try:
        with open(fn, "r") as template_app_ini:
            template = template_app_ini.read()
    except FileNotFoundError:
        abort(404)
    return template.replace("\n", "<br>")
