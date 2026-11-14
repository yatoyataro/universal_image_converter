"""Tests for collision-safe output path resolution (audit issue H5)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter_core import resolve_output_path


def test_simple_name_when_no_collision(tmp_path):
    src = tmp_path / "photo.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = resolve_output_path(src, out_dir, "webp")
    assert result == out_dir / "photo.webp"


def test_first_collision_gets_suffix(tmp_path):
    src = tmp_path / "a" / "photo.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.webp").write_bytes(b"x")
    result = resolve_output_path(src, out_dir, "webp")
    assert result == out_dir / "photo-1.webp"


def test_repeated_collisions_increment(tmp_path):
    src = tmp_path / "photo.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "photo.webp").write_bytes(b"x")
    (out_dir / "photo-1.webp").write_bytes(b"x")
    result = resolve_output_path(src, out_dir, "webp")
    assert result == out_dir / "photo-2.webp"


def test_jpeg_source_maps_to_jpg_extension(tmp_path):
    src = tmp_path / "photo.jpeg"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = resolve_output_path(src, out_dir, "jpg")
    assert result == out_dir / "photo.jpg"


def test_collision_check_is_case_insensitive_on_windows(tmp_path):
    src = tmp_path / "photo.png"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "PHOTO.WEBP").write_bytes(b"x")
    result = resolve_output_path(src, out_dir, "webp")
    assert os.path.basename(result) != "photo.webp"
