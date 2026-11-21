import glob
import os
import re
from secrets import token_hex

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from dashmachine import db
from dashmachine.main.models import Apps, DataSources, Files
from dashmachine.main.utils import check_groups, get_data_source, mark_update_message_read, safe_join
from dashmachine.paths import cache_folder
from dashmachine.settings_system.models import Settings
from dashmachine.user_system.models import User  # noqa: F401 - registers the user loader

main = Blueprint("main", __name__)

SAFE_EXTENSION = re.compile(r"^[A-Za-z0-9]{1,8}$")


def _get_or_404(model, raw_id):
    try:
        row_id = int(raw_id)
    except (TypeError, ValueError):
        abort(404)
    row = db.session.get(model, row_id)
    if row is None:
        abort(404)
    return row


# ------------------------------------------------------------------------------
# intial routes and functions (before/after request)
# ------------------------------------------------------------------------------
@main.route("/")
@main.route("/home", methods=["GET"])
def home():
    settings = Settings.query.first()
    if settings and not check_groups(settings.home_access_groups, current_user):
        return redirect(url_for("error_pages.unauthorized"))
    return render_template("main/home.html")


@main.route("/app_view", methods=["GET"])
def app_view():
    """Full-page wrapper for one app, addressable as ?<id> or ?app_id=<id>."""
    settings = Settings.query.first()
    if settings and not check_groups(settings.home_access_groups, current_user):
        return redirect(url_for("user_system.login"))
    # historically linked as /app_view?3, which arrives as a bare query string
    app_id = request.args.get("app_id") or next(iter(request.args), None)
    app_db = _get_or_404(Apps, app_id)
    return render_template(
        "main/app-view.html", url=f"{app_db.prefix}{app_db.url}", title=app_db.name
    )


@main.route("/load_data_source", methods=["GET"])
def load_data_source():
    return get_data_source(_get_or_404(DataSources, request.args.get("id")))


@main.route("/update_message_read", methods=["GET"])
def update_message_read():
    mark_update_message_read()
    return "ok"


# ------------------------------------------------------------------------------
# TCDROP routes
# ------------------------------------------------------------------------------
@main.route("/tcdrop/cacheFile", methods=["POST"])
def cacheFile():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        abort(400)

    extension = os.path.splitext(upload.filename)[1].lstrip(".").lower()
    if not SAFE_EXTENSION.match(extension):
        extension = "bin"

    random_hex = token_hex(16)
    fn = f"{random_hex}.{extension}"
    path = os.path.join(cache_folder, fn)
    upload.save(path)

    html = render_template(
        "main/tcdrop-file-row.html", orig_fn=upload.filename, fn=fn, id=random_hex
    )
    db.session.add(Files(name=upload.filename, path=path, cache=fn, folder="cache"))
    db.session.commit()
    return jsonify(data={"cached": fn, "html": html})


@main.route("/tcdrop/clearCache", methods=["GET"])
def clearCache():
    for file in glob.glob(os.path.join(cache_folder, "*")):
        if ".no" not in file:
            try:
                os.remove(file)
            except OSError:
                pass
    Files.query.filter_by(folder="cache").delete()
    db.session.commit()
    return "success"


@main.route("/tcdrop/deleteCachedFile", methods=["GET"])
def deleteCachedFile():
    try:
        path = safe_join(cache_folder, request.args.get("file", ""))
    except ValueError:
        abort(400)
    Files.query.filter_by(path=path).delete()
    db.session.commit()
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    return "success"
