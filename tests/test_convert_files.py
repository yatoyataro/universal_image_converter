"""Tests for batch conversion with a thread pool and cancellation (M10, feature 8)."""
import sys
import threading
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from converter_core import convert_files


def _png(tmp_path, name, color="red"):
    img = Image.new("RGB", (4, 4), color)
    path = tmp_path / name
    img.save(path)
    return path


def test_converts_all_files_and_counts(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    files = [_png(tmp_path, f"img{i}.png", color=f"#{i:02x}4040" if i else "red")
             for i in range(5)]
    result = convert_files(files, out_dir, "webp", max_workers=3)
    assert result.converted == 5
    assert result.failed == 0
    assert len(list(out_dir.glob("*.webp"))) == 5


def test_progress_called_once_per_file(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    files = [_png(tmp_path, f"img{i}.png") for i in range(4)]
    seen = []
    convert_files(files, out_dir, "webp", max_workers=2,
                  progress_callback=lambda done, total: seen.append((done, total)))
    assert sorted(done for done, _ in seen) == [1, 2, 3, 4]
    assert all(total == 4 for _, total in seen)


def test_cancel_before_start_processes_nothing(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    files = [_png(tmp_path, f"img{i}.png") for i in range(3)]
    cancel = threading.Event()
    cancel.set()
    result = convert_files(files, out_dir, "webp", max_workers=2, cancel_event=cancel)
    assert result.cancelled == 3
    assert result.converted == 0
    assert len(list(out_dir.glob("*.webp"))) == 0


def test_cancel_mid_run_stops_remaining(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    files = [_png(tmp_path, f"img{i}.png") for i in range(6)]
    cancel = threading.Event()

    def cancel_after_first(done, total):
        if done >= 1:
            cancel.set()

    result = convert_files(files, out_dir, "webp", max_workers=1,
                           cancel_event=cancel, progress_callback=cancel_after_first)
    assert result.cancelled >= 1
    assert result.converted + result.cancelled == 6


def test_errors_collected_others_still_convert(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    good = _png(tmp_path, "good.png")
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    result = convert_files([good, bad], out_dir, "webp", max_workers=2)
    assert result.converted == 1
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0][0] == bad


def test_copy_and_skip_statuses_counted(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    png = _png(out_dir, "same.png")  # source IS out_dir/same.png -> skipped
    jpg = _png(tmp_path, "copy.png")  # same ext, different folder -> copied
    result = convert_files([png, jpg], out_dir, "png", max_workers=2)
    assert result.skipped == 1
    assert result.copied == 1
