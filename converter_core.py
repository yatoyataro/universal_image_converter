"""Pure conversion helpers for Universal Image Converter.

This module contains no GUI code so it can be tested headlessly.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

# Modes that carry transparency (or may, in the palette case) and must be
# flattened before a JPEG save, which has no alpha channel.
_HAS_ALPHA = {"RGBA", "LA", "PA", "P"}


def prepare_image_for_save(img: Image.Image, target_ext: str) -> Image.Image:
    """Return an image whose mode is saveable for the target format.

    Applies EXIF orientation first so rotated phone photos come out
    upright (audit issue H3), then fixes the mode conversion table
    (audit issue M8): JPEG flattens alpha to RGB, PNG maps CMYK to RGB
    instead of RGBA, palette PNGs keep their palette, WebP gets RGB/RGBA.
    """
    result = ImageOps.exif_transpose(img) or img
    ext = normalize_target_ext(target_ext)

    if ext == "jpg":
        if result.mode in _HAS_ALPHA:
            return result.convert("RGB")
        return result
    if ext == "png":
        if result.mode == "CMYK":
            return result.convert("RGB")
        return result
    # webp
    if result.mode == "CMYK":
        return result.convert("RGB")
    if result.mode in {"P", "PA", "LA"}:
        return result.convert("RGBA")
    return result


def normalize_target_ext(ext: str) -> str:
    """Map a user-facing target extension to its canonical form."""
    cleaned = ext.lower().lstrip(".")
    return "jpg" if cleaned in {"jpg", "jpeg"} else cleaned


def resolve_output_path(source_path: str | Path, output_dir: str | Path,
                        target_ext: str) -> Path:
    """Build the output path for a source file, suffixing on collisions.

    If ``<base>.<ext>`` already exists in ``output_dir``, returns
    ``<base>-1.<ext>``, ``<base>-2.<ext>``, ... so existing files are
    never silently overwritten (audit issue H5).
    """
    src = Path(source_path)
    out_dir = Path(output_dir)
    ext = normalize_target_ext(target_ext)
    base = src.stem

    candidate = out_dir / f"{base}.{ext}"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = out_dir / f"{base}-{counter}.{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


@dataclass(frozen=True)
class ConversionResult:
    """Outcome of converting one file."""
    status: str            # "converted" | "copied" | "skipped"
    output_path: Path | None


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.exists() and a.resolve() == b.resolve()
    except OSError:
        return False


def convert_file(source_path: str | Path, output_dir: str | Path,
                 target_ext: str) -> ConversionResult:
    """Convert one image file, or copy it when the extension already matches.

    Never overwrites an existing output file (collision suffixes are added
    by resolve_output_path). Raises on failure so the caller can log it.
    """
    src = Path(source_path)
    out_dir = Path(output_dir)
    ext = normalize_target_ext(target_ext)

    if not src.is_file():
        raise FileNotFoundError(f"Source image not found: {src}")

    # If the plain output name would be the source file itself (same folder,
    # same extension), there is nothing to do -- and the collision suffixer
    # must not treat the source as someone else's collision.
    default_output = out_dir / f"{src.stem}.{ext}"
    if _same_file(default_output, src):
        return ConversionResult("skipped", None)

    output_path = resolve_output_path(src, out_dir, ext)

    source_ext = src.suffix.lower().lstrip(".")
    same_as_target = source_ext == ext or (ext == "jpg" and source_ext == "jpeg")

    if same_as_target:
        shutil.copy2(src, output_path)
        return ConversionResult("copied", output_path)

    with Image.open(src) as img:
        prepared = prepare_image_for_save(img, ext)
        save_format = "JPEG" if ext == "jpg" else ext.upper()
        save_kwargs: dict = {}
        if ext in {"jpg", "webp"}:
            save_kwargs["quality"] = 90
        prepared.save(output_path, format=save_format, **save_kwargs)
    return ConversionResult("converted", output_path)


def describe_error(exc: BaseException) -> tuple[str, str]:
    """Map an exception to a (reason, suggestion) pair for end users."""
    if isinstance(exc, Image.DecompressionBombError):
        return (
            "The image is too large to open safely.",
            "Use a smaller image, or downscale it with other software first.",
        )
    if isinstance(exc, FileNotFoundError):
        return (
            "The source file or destination folder could not be found.",
            "Re-select the image or choose a destination folder that still exists.",
        )
    if isinstance(exc, PermissionError):
        return (
            "Windows blocked access to the file or the destination folder.",
            "Close the image in other apps or pick a folder where you have write access.",
        )
    if isinstance(exc, Image.UnidentifiedImageError):
        return (
            "Pillow could not recognize this file as a supported image.",
            "Check that the file is a valid image and try again with another source file.",
        )
    if isinstance(exc, shutil.SameFileError):
        return (
            "The app tried to copy the file onto itself in the same location.",
            "Use a different output folder or a different filename to avoid copying onto the same file.",
        )
    if isinstance(exc, IsADirectoryError):
        return (
            "The selected path points to a folder instead of an image file.",
            "Make sure the selected item is an image file, not a folder.",
        )
    if isinstance(exc, OSError):
        return (
            "The image may be damaged, locked by another app, or not supported by this format.",
            "Try another image file or another target format, and make sure the file is not locked.",
        )
    return (
        "An unexpected error occurred while processing the file.",
        "Try the file again or choose a different source image.",
    )
