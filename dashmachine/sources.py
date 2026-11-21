"""Bundles of JS and CSS sources, and the shared template context.

Bundles used to be concatenated and minified on every request, which cost CPU
per page view and pulled in three unmaintained dependencies (jsmin, htmlmin and
a hand-rolled cssmin). They are now emitted as ordinary static file tags with a
content-derived cache-busting query, so browsers cache them and a deploy
invalidates them automatically.

Load order within a bundle is preserved here and must be preserved in Jinja.
"""
import json
import os
import random

from flask import url_for
from flask_login import current_user
from wtforms.fields.choices import SelectChoice

from dashmachine.main.forms import TagsForm
from dashmachine.main.models import Apps, Tags
from dashmachine.main.utils import check_groups, get_update_message_html
from dashmachine.paths import backgrounds_images_folder, static_folder
from dashmachine.settings_system.models import Settings

GLOBAL_JS = [
    "global/dashmachine.js",
    "global/tcdrop.js",
]

GLOBAL_CSS = [
    "global/dashmachine-theme.css",
    "global/dashmachine.css",
    "global/tcdrop.css",
]

def _asset_url(kind, source):
    """URL for a static asset, versioned by the file's mtime."""
    path = os.path.join(static_folder, kind, source)
    try:
        version = int(os.stat(path).st_mtime)
    except OSError:
        version = 0
    return url_for("static", filename=f"{kind}/{source}", v=version)


def process_js_sources(process_bundle=None, src=None, app_global=False):
    if src:
        process_bundle = [src]
    elif app_global is True:
        process_bundle = GLOBAL_JS

    return "".join(
        f'<script src="{_asset_url("js", source)}"></script>\n'
        for source in process_bundle
    )


def process_css_sources(process_bundle=None, src=None, app_global=False):
    if src:
        process_bundle = [src]
    elif app_global is True:
        process_bundle = GLOBAL_CSS

    return "".join(
        f'<link rel="stylesheet" type="text/css" href="{_asset_url("css", source)}">\n'
        for source in process_bundle
    )


def tag_sort_func(tag):
    if not tag.sort_pos:
        tag.sort_pos = 99999
    return tag.sort_pos


def context_processor():
    apps = []
    temp_tags = []
    tags = []
    for app_db in Apps.query.all():
        if app_db.urls:
            url_list = app_db.urls.replace("},{", "}%,%{").split("%,%")
            app_db.urls_json = [json.loads(url) for url in url_list]
        if not app_db.groups:
            app_db.groups = None
        if check_groups(app_db.groups, current_user):
            apps.append(app_db)
            if app_db.tags:
                temp_tags += app_db.tags.split(",")

    tags_form = TagsForm()
    if temp_tags:
        temp_tags = list(dict.fromkeys(tag.strip() for tag in temp_tags))
    tags_form.tags.choices += [SelectChoice(tag, tag) for tag in temp_tags]

    for tag in temp_tags:
        tag_db = Tags.query.filter_by(name=tag).first()
        if tag_db:
            tags.append(tag_db)
    tags.sort(key=tag_sort_func)

    settings = Settings.query.first()
    if settings and settings.background == "random":
        try:
            backgrounds = os.listdir(backgrounds_images_folder)
        except OSError:
            backgrounds = []
        if not backgrounds:
            settings.background = None
        else:
            settings.background = (
                f"static/images/backgrounds/{random.choice(backgrounds)}"
            )

    return dict(
        process_js_sources=process_js_sources,
        process_css_sources=process_css_sources,
        apps=apps,
        settings=settings,
        tags=tags,
        tags_form=tags_form,
        update_message=get_update_message_html(),
    )
