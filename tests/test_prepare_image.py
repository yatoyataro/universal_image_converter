"""Tests for mode conversion and EXIF orientation (audit issues H3, M8)."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter_core import prepare_image_for_save


def _exif_image_with_orientation(tmp_path, orientation=6):
    """4x2 RGB image tagged 'rotate 90 CW' so transposition swaps its sides."""
    img = Image.new("RGB", (4, 2), "red")
    exif = img.getexif()
    exif[0x0112] = orientation  # 274 = Orientation
    path = tmp_path / "oriented.jpg"
    img.save(path, exif=exif)
    return Image.open(path)


def test_exif_orientation_applied_and_tag_cleared(tmp_path):
    src = _exif_image_with_orientation(tmp_path)
    result = prepare_image_for_save(src, "webp")
    assert result.size == (2, 4)  # sides swapped by the rotation
    assert not result.getexif().get(0x0112, 1) != 1  # orientation tag neutralized


def test_image_without_exif_unchanged(tmp_path):
    src = Image.new("RGB", (4, 2), "blue")
    result = prepare_image_for_save(src, "png")
    assert result.size == (4, 2)
    assert result.mode == "RGB"


def test_rgba_to_jpg_becomes_rgb():
    result = prepare_image_for_save(Image.new("RGBA", (4, 4)), "jpg")
    assert result.mode == "RGB"


def test_la_to_jpg_becomes_rgb_instead_of_failing():
    # LA mode crashed the old JPEG save path (M8)
    result = prepare_image_for_save(Image.new("LA", (4, 4)), "jpg")
    assert result.mode == "RGB"


def test_palette_with_transparency_to_jpg_becomes_rgb():
    base = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
    result = prepare_image_for_save(base.convert("P"), "jpg")
    assert result.mode == "RGB"


def test_cmyk_to_png_becomes_rgb_not_rgba():
    # Old code converted CMYK -> RGBA which shifts colors (M8)
    result = prepare_image_for_save(Image.new("CMYK", (4, 4)), "png")
    assert result.mode == "RGB"


def test_palette_png_stays_palette():
    # Old code needlessly converted P -> RGBA for PNG (M8)
    src = Image.new("RGBA", (4, 4)).convert("P")
    result = prepare_image_for_save(src, "png")
    assert result.mode == "P"


def test_cmyk_to_webp_becomes_rgb():
    result = prepare_image_for_save(Image.new("CMYK", (4, 4)), "webp")
    assert result.mode == "RGB"
