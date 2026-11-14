"""Pure conversion helpers for Universal Image Converter.

This module contains no GUI code so it can be tested headlessly.
"""
from __future__ import annotations

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class ConvertOptions:
    """User-selectable conversion settings (audit Step 4 features)."""
    quality: int = 90
    lossless_webp: bool = False
    max_dimension: int | None = None   # downscale so neither side exceeds this
    keep_metadata: bool = False        # preserve EXIF (orientation stays fixed)
    overwrite: bool = False            # replace existing outputs instead of suffixing


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.exists() and a.resolve() == b.resolve()
    except OSError:
        return False


def convert_file(source_path: str | Path, output_dir: str | Path,
                 target_ext: str, options: ConvertOptions | None = None) -> ConversionResult:
    """Convert one image file, or copy it when the extension already matches.

    With default options, existing outputs are never overwritten (collision
    suffixes are added by resolve_output_path). Raises on failure so the
    caller can log it.
    """
    opts = options or ConvertOptions()
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

    if opts.overwrite:
        output_path = out_dir / f"{src.stem}.{ext}"
    else:
        output_path = resolve_output_path(src, out_dir, ext)

    source_ext = src.suffix.lower().lstrip(".")
    same_as_target = source_ext == ext or (ext == "jpg" and source_ext == "jpeg")

    if same_as_target:
        shutil.copy2(src, output_path)
        return ConversionResult("copied", output_path)

    with Image.open(src) as img:
        prepared = prepare_image_for_save(img, ext)
        if opts.max_dimension is not None and max(prepared.size) > opts.max_dimension:
            prepared.thumbnail((opts.max_dimension, opts.max_dimension))
        save_format = "JPEG" if ext == "jpg" else ext.upper()
        save_kwargs: dict = {}
        if ext in {"jpg", "webp"}:
            save_kwargs["quality"] = opts.quality
        if ext == "webp" and opts.lossless_webp:
            save_kwargs["lossless"] = True
        if opts.keep_metadata:
            exif_bytes = prepared.info.get("exif")
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
        prepared.save(output_path, format=save_format, **save_kwargs)
    return ConversionResult("converted", output_path)


@dataclass
class BatchResult:
    """Aggregate outcome of a batch conversion run (mutated as it runs)."""
    converted: int = 0
    copied: int = 0
    skipped: int = 0
    cancelled: int = 0
    failed: int = 0
    errors: list[tuple[Path, BaseException]] = field(default_factory=list)


def convert_files(files: list[str | Path], output_dir: str | Path,
                  target_ext: str, *, max_workers: int = 4,
                  cancel_event: threading.Event | None = None,
                  progress_callback=None,
                  options: ConvertOptions | None = None) -> BatchResult:
    """Convert many files across a thread pool (Pillow releases the GIL).

    ``progress_callback(done, total)`` fires once per finished file from
    worker threads. If ``cancel_event`` is set, unstarted files are counted
    as cancelled instead of being processed.
    """
    result = BatchResult()
    total = len(files)
    if total == 0:
        return result

    done = 0
    done_lock = threading.Lock()

    class _Cancelled(Exception):
        pass

    def run_one(path):
        # Check inside the task: by the time futures run, they are already
        # queued, so a pre-submit check alone would still convert everything.
        if cancel_event is not None and cancel_event.is_set():
            raise _Cancelled()
        return convert_file(path, output_dir, target_ext, options)

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(run_one, path): Path(path) for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                outcome = future.result()
            except _Cancelled:
                result.cancelled += 1
            except Exception as exc:
                result.failed += 1
                result.errors.append((path, exc))
            else:
                if outcome.status == "converted":
                    result.converted += 1
                elif outcome.status == "copied":
                    result.copied += 1
                else:
                    result.skipped += 1
            with done_lock:
                done += 1
                if progress_callback is not None:
                    progress_callback(done, total)
    return result


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
