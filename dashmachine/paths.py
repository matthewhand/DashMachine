"""Filesystem locations used by DashMachine.

Everything is derived from the package location so the app works the same in a
container and from a checkout. ``DASHMACHINE_USER_DATA`` overrides the writable
data directory (used by ``/opt/stacks/dashmachine`` and by the test suite).
"""
import os
from pathlib import Path

# root path of the application (the directory holding the dashmachine package)
root_folder = str(Path(__file__).resolve().parent.parent)

dashmachine_folder = os.path.join(root_folder, "dashmachine")

template_apps_folder = os.path.join(root_folder, "template_apps")

platform_folder = os.path.join(dashmachine_folder, "platform")

user_data_folder = os.environ.get("DASHMACHINE_USER_DATA") or os.path.join(
    dashmachine_folder, "user_data"
)

auth_cache = os.path.join(user_data_folder, "auth_cache")

static_folder = os.path.join(dashmachine_folder, "static")

images_folder = os.path.join(static_folder, "images")

apps_images_folder = os.path.join(images_folder, "apps")

backgrounds_images_folder = os.path.join(images_folder, "backgrounds")

icons_images_folder = os.path.join(images_folder, "icons")

cache_folder = os.path.join(static_folder, "cache")

user_images_folder = os.path.join(images_folder, "user")

for folder in (user_data_folder, auth_cache, cache_folder):
    os.makedirs(folder, exist_ok=True)
