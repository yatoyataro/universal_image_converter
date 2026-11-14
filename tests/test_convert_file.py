"""Tests for convert_file and error classification (H3, H5, L13 integration)."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter_core import convert_file, describe_error


def _png(tmp_path, name="src.png", size=(4, 4), color="red"):
    img = Image.new("RGB", size, color)
    path = tmp_path / name
    img.save(path)
    return path


def test_converts_png_to_webp(tmp_path):
    src = _png(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp")
    assert result.status == "converted"
    assert result.output_path == out_dir / "src.webp"
    with Image.open(result.output_path) as saved:
        assert saved.format == "WEBP"


def test_copies_when_extension_already_matches(tmp_path):
    src = _png(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "png")
    assert result.status == "copied"
    assert (out_dir / "src.png").exists()


def test_skips_when_output_is_source_itself(tmp_path):
    src = _png(tmp_path, name="same.png")
    result = convert_file(src, tmp_path, "png")
    assert result.status == "skipped"
    assert result.output_path is None


def test_existing_output_not_overwritten(tmp_path):
    src = _png(tmp_path, color="red")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # A pre-existing webp with a distinct color must survive untouched.
    Image.new("RGB", (4, 4), "blue").save(out_dir / "src.webp")
    result = convert_file(src, out_dir, "webp")
    assert result.status == "converted"
    assert result.output_path == out_dir / "src-1.webp"
    with Image.open(result.output_path) as saved:
        pixel = saved.convert("RGB").getpixel((0, 0))
        assert pixel[0] > 200 and pixel[1] < 100  # red, not the blue survivor


def test_missing_source_raises_filenotfound(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        convert_file(tmp_path / "ghost.png", tmp_path, "webp")


def test_exif_orientation_applied_during_conversion(tmp_path):
    img = Image.new("RGB", (4, 2), "red")
    exif = img.getexif()
    exif[0x0112] = 6
    src = tmp_path / "oriented.jpg"
    img.save(src, exif=exif)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp")
    with Image.open(result.output_path) as saved:
        assert saved.size == (2, 4)


def test_describe_error_decompression_bomb():
    reason, suggestion = describe_error(Image.DecompressionBombError("huge"))
    assert "large" in reason.lower()
    assert suggestion


def test_describe_error_unidentified_image():
    reason, _ = describe_error(Image.UnidentifiedImageError("nope"))
    assert "recognize" in reason.lower() or "image" in reason.lower()


def test_describe_error_generic():
    reason, _ = describe_error(ValueError("weird"))
    assert reason
