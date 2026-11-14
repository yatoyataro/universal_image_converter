"""Central UI palette for the Universal Image Converter.

Every color is a ``(light, dark)`` tuple. CustomTkinter widgets accept these
tuples natively and swap to the right half automatically whenever the
appearance mode changes, so theme switching needs no manual re-configure
pass. The GUI must never hardcode a hex color -- import this module instead.
"""

# Main surfaces
BG_WINDOW: tuple[str, str] = ("#f1f2f4", "#111111")
BG_PANEL: tuple[str, str] = ("#ffffff", "#1b1b1b")
BG_PANEL_ALT: tuple[str, str] = ("#e9eaee", "#151515")
BORDER_PANEL: tuple[str, str] = ("#dcdde1", "#2d2d2d")
BG_CARD: tuple[str, str] = ("#f8f9fa", "#202020")
BORDER_CARD: tuple[str, str] = ("#e3e4e8", "#2f2f2f")
BORDER_INPUT: tuple[str, str] = ("#c9cbd1", "#4a4a4a")

# Nested elements (preview cards, thumbnail wells)
BG_NESTED: tuple[str, str] = ("#eef0f2", "#262626")
BORDER_NESTED: tuple[str, str] = ("#dfe1e5", "#343434")
BG_THUMB: tuple[str, str] = ("#eaecef", "#1f1f1f")

# Text
TEXT_MUTED: tuple[str, str] = ("#5f6168", "#9a9a9a")
TEXT_FAINT: tuple[str, str] = ("#75777e", "#a5a5a5")

# Actions
ACCENT: tuple[str, str] = ("#2EA043", "#2EA043")
ACCENT_HOVER: tuple[str, str] = ("#237A32", "#237A32")
DANGER: tuple[str, str] = ("#c23b34", "#B93838")
DANGER_HOVER: tuple[str, str] = ("#9e2d27", "#9B2C2C")

# Chips (item-count pill)
CHIP_BG: tuple[str, str] = ("#e7e8ec", "#2a2a2a")
CHIP_TEXT: tuple[str, str] = ("#3c3e44", "#d7d7d7")

# Preview-failure states
WARNING_BG: tuple[str, str] = ("#fdf4e3", "#2b2320")
WARNING_BORDER: tuple[str, str] = ("#d9a441", "#8a5a2a")
WARNING_TEXT: tuple[str, str] = ("#8a6d1a", "#c9a227")

# Empty state
EMPTY_BG: tuple[str, str] = ("#f2f3f5", "#252525")
EMPTY_BORDER: tuple[str, str] = ("#e0e2e6", "#333333")

# (name, value) pairs consumed by tests; keep in sync with the constants above.
ALL_COLORS: list[tuple[str, tuple[str, str]]] = [
    ("BG_WINDOW", BG_WINDOW), ("BG_PANEL", BG_PANEL), ("BG_PANEL_ALT", BG_PANEL_ALT),
    ("BORDER_PANEL", BORDER_PANEL), ("BORDER_INPUT", BORDER_INPUT),
    ("BG_CARD", BG_CARD), ("BORDER_CARD", BORDER_CARD), ("BG_NESTED", BG_NESTED),
    ("BORDER_NESTED", BORDER_NESTED), ("BG_THUMB", BG_THUMB), ("TEXT_MUTED", TEXT_MUTED),
    ("TEXT_FAINT", TEXT_FAINT), ("ACCENT", ACCENT), ("ACCENT_HOVER", ACCENT_HOVER),
    ("DANGER", DANGER), ("DANGER_HOVER", DANGER_HOVER), ("CHIP_BG", CHIP_BG),
    ("CHIP_TEXT", CHIP_TEXT), ("WARNING_BG", WARNING_BG), ("WARNING_BORDER", WARNING_BORDER),
    ("WARNING_TEXT", WARNING_TEXT), ("EMPTY_BG", EMPTY_BG), ("EMPTY_BORDER", EMPTY_BORDER),
]
