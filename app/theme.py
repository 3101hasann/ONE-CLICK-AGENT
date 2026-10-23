"""Central design tokens. Every colour/font used by the UI comes from here."""

BG = "#101410"
CARD = "#192119"
SURFACE = "#202B20"
SURFACE_HOVER = "#27352A"
ACCENT = "#A3E635"
ACCENT_HOVER = "#B8F05A"
ACCENT_TEXT = "#14220B"
TEXT = "#F0FDF4"
TEXT_MUTED = "#A3B5A4"
TEXT_DIM = "#6F8271"
BORDER = "#344638"
ERROR = "#F87171"
WARNING = "#FBBF24"
INFO = "#7DD3FC"
DISABLED_BG = "#1C251D"
DISABLED_TEXT = "#55665A"

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Cascadia Mono"

RADIUS = 12
RADIUS_SM = 8
PAD = 16
GAP = 10

STATUS_COLORS = {
    "IDLE": ACCENT,
    "RUNNING": ACCENT,
    "PROCESSING": INFO,
    "PAUSED": WARNING,
    "WAITING_FOR_REVIEW": INFO,
    "ERROR": ERROR,
    "STOPPED": TEXT_MUTED,
}

STATUS_LABELS = {
    "IDLE": "READY",
    "RUNNING": "RUNNING",
    "PROCESSING": "PROCESSING",
    "PAUSED": "PAUSED",
    "WAITING_FOR_REVIEW": "REVIEW",
    "ERROR": "ERROR",
    "STOPPED": "STOPPED",
}

LOG_LEVEL_COLORS = {
    "INFO": TEXT_MUTED,
    "OK": ACCENT,
    "WARN": WARNING,
    "ERROR": ERROR,
}


def font(size: int = 13, weight: str = "normal") -> tuple:
    return (FONT_FAMILY, size, weight)


def mono(size: int = 12) -> tuple:
    return (MONO_FAMILY, size)


def primary_button(**overrides) -> dict:
    style = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_TEXT,
                 text_color_disabled=DISABLED_TEXT, corner_radius=RADIUS_SM,
                 font=font(13, "bold"), height=38)
    style.update(overrides)
    return style


def secondary_button(**overrides) -> dict:
    style = dict(fg_color=SURFACE, hover_color=SURFACE_HOVER, text_color=TEXT,
                 text_color_disabled=DISABLED_TEXT, border_color=BORDER, border_width=1,
                 corner_radius=RADIUS_SM, font=font(12), height=34)
    style.update(overrides)
    return style


def danger_button(**overrides) -> dict:
    return secondary_button(text_color=ERROR, **overrides)
