import os

from PIL import Image

from dashmachine.main.utils import resize_template_app_images


def _write_icon(path, size, colour=(200, 30, 30)):
    Image.new("RGBA", size, colour).save(path, format="PNG")


def test_oversized_icons_are_downscaled(images_dir):
    apps = images_dir / "apps"
    big = apps / "checked.png"
    _write_icon(big, (200, 120))

    resize_template_app_images()

    with Image.open(big) as image:
        assert max(image.size) <= 64


def test_small_icons_are_not_rewritten(images_dir):
    apps = images_dir / "apps"
    small = apps / "untouched.png"
    _write_icon(small, (32, 32))
    before = small.read_bytes()
    mtime = os.stat(small).st_mtime_ns

    resize_template_app_images()

    assert small.read_bytes() == before
    assert os.stat(small).st_mtime_ns == mtime


def test_second_run_changes_nothing(images_dir):
    apps = images_dir / "apps"
    big = apps / "then-small.png"
    _write_icon(big, (300, 300))

    resize_template_app_images()
    first = {p.name: p.read_bytes() for p in apps.iterdir() if p.is_file()}

    resize_template_app_images()
    second = {p.name: p.read_bytes() for p in apps.iterdir() if p.is_file()}

    assert first == second


def test_corrupt_icon_is_skipped_and_others_still_processed(images_dir, caplog):
    apps = images_dir / "apps"
    broken = apps / "aaa-broken.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n truncated")
    big = apps / "zzz-big.png"
    _write_icon(big, (256, 256))

    resize_template_app_images()

    with Image.open(big) as image:
        assert max(image.size) <= 64
    # the bad file is left alone rather than deleted
    assert broken.read_bytes() == b"\x89PNG\r\n\x1a\n truncated"
    assert "skipping unreadable icon" in caplog.text


def test_leftover_temp_files_are_removed(images_dir):
    leftover = images_dir / "apps" / "icon.png.tmp"
    leftover.write_bytes(b"partial")
    resize_template_app_images()
    assert not leftover.exists()


def test_missing_folder_is_not_fatal(tmp_path, monkeypatch):
    from dashmachine.main import utils

    monkeypatch.setattr(utils, "images_folder", str(tmp_path / "nope"))
    resize_template_app_images()
