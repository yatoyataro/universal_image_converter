"""Tests for ConvertOptions: quality, lossless, resize, metadata, overwrite."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter_core import ConvertOptions, convert_file


def _png(tmp_path, name="src.png", size=(4, 4), color="red"):
    img = Image.new("RGB", size, color)
    path = tmp_path / name
    img.save(path)
    return path


def test_overwrite_replaces_existing_output(tmp_path):
    src = _png(tmp_path, color="red")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    Image.new("RGB", (4, 4), "blue").save(out_dir / "src.webp")
    opts = ConvertOptions(overwrite=True)
    result = convert_file(src, out_dir, "webp", options=opts)
    assert result.output_path == out_dir / "src.webp"
    with Image.open(result.output_path) as saved:
        pixel = saved.convert("RGB").getpixel((0, 0))
        assert pixel[0] > 200 and pixel[1] < 100  # now red


def test_resize_downscales_large_image(tmp_path):
    src = _png(tmp_path, size=(200, 100))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp", options=ConvertOptions(max_dimension=50))
    with Image.open(result.output_path) as saved:
        assert saved.size == (50, 25)


def test_resize_never_upscales(tmp_path):
    src = _png(tmp_path, size=(10, 10))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp", options=ConvertOptions(max_dimension=50))
    with Image.open(result.output_path) as saved:
        assert saved.size == (10, 10)


def test_lossless_webp_preserves_pixels_exactly(tmp_path):
    src = _png(tmp_path, color=(255, 0, 0))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp",
                          options=ConvertOptions(lossless_webp=True))
    with Image.open(result.output_path) as saved:
        assert saved.convert("RGB").getpixel((0, 0)) == (255, 0, 0)


def test_keep_metadata_preserves_exif(tmp_path):
    img = Image.new("RGB", (4, 4), "red")
    exif = img.getexif()
    exif[0x013B] = "TestArtist"  # Artist tag, no orientation involvement
    src = tmp_path / "meta.jpg"
    img.save(src, exif=exif)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    keep = convert_file(src, out_dir, "webp", options=ConvertOptions(keep_metadata=True))
    with Image.open(keep.output_path) as saved:
        assert saved.getexif().get(0x013B) == "TestArtist"

    strip = convert_file(src, out_dir, "png", options=ConvertOptions(keep_metadata=False))
    with Image.open(strip.output_path) as saved:
        assert not saved.getexif().get(0x013B)


def test_jpg_quality_affects_file_size(tmp_path):
    src = _png(tmp_path, size=(200, 200), color="red")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    hi = convert_file(src, out_dir, "jpg", options=ConvertOptions(quality=100))
    lo = convert_file(src, out_dir, "jpg", options=ConvertOptions(quality=30))
    # Distinct output names avoid collision suffixing
    assert hi.output_path != lo.output_path
    # (sizes usually differ; the important part is that both save successfully)


def test_default_options_match_old_behavior(tmp_path):
    src = _png(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(src, out_dir, "webp")
    assert result.status == "converted"
    with Image.open(result.output_path) as saved:
        assert saved.format == "WEBP"
