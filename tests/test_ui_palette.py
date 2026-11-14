"""Tests for the central light/dark palette and the no-hardcoded-colors rule."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui_palette

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_every_palette_color_is_a_light_dark_pair():
    for name, value in ui_palette.ALL_COLORS:
        assert isinstance(value, tuple), f"{name} must be a tuple"
        assert len(value) == 2, f"{name} must have exactly (light, dark) values"
        for color in value:
            assert isinstance(color, str) and HEX_RE.match(color), f"{name}: bad color {color!r}"


def test_main_surfaces_differ_between_modes():
    """Light and dark variants must not be identical for surfaces and text."""
    for name in ("BG_WINDOW", "BG_PANEL", "BG_CARD", "TEXT_MUTED"):
        light, dark = getattr(ui_palette, name)
        assert light != dark, f"{name} should change between light and dark"


def test_app_v2_has_no_hardcoded_hex_colors():
    """The GUI must pull every color from ui_palette so theme switching works."""
    source = Path(__file__).resolve().parent.parent.joinpath("app_v2.py").read_text(encoding="utf-8")
    offenders = re.findall(r'"#[0-9a-fA-F]{6}"', source)
    assert offenders == [], f"hardcoded colors in app_v2.py: {offenders}"


def test_palette_constants_are_exposed():
    expected = [
        "BG_WINDOW", "BG_PANEL", "BORDER_PANEL", "BG_CARD", "BORDER_CARD",
        "BG_NESTED", "BORDER_NESTED", "BG_THUMB", "TEXT_MUTED", "TEXT_FAINT",
        "ACCENT", "ACCENT_HOVER", "DANGER", "DANGER_HOVER",
        "CHIP_BG", "CHIP_TEXT", "WARNING_BG", "WARNING_BORDER", "WARNING_TEXT",
        "EMPTY_BG", "EMPTY_BORDER",
    ]
    missing = [name for name in expected if not hasattr(ui_palette, name)]
    assert missing == [], f"missing palette constants: {missing}"
