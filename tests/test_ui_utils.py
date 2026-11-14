"""Tests for small UI helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_v2 import ImageConverterApp


def test_ellipsis_middle_leaves_short_paths_alone():
    assert ImageConverterApp._ellipsis_middle("C:\\out", 42) == "C:\\out"
    assert ImageConverterApp._ellipsis_middle("", 42) == ""


def test_ellipsis_middle_keeps_start_and_end():
    path = "C:\\Users\\someone\\Documents\\very\\deep\\nested\\folder\\photos"
    out = ImageConverterApp._ellipsis_middle(path, 25)
    assert len(out) <= 25
    assert out.startswith("C:\\Users")
    assert out.endswith("photos")
    assert "…" in out


def test_ellipsis_middle_exact_length_boundary():
    path = "x" * 25
    assert ImageConverterApp._ellipsis_middle(path, 25) == path
