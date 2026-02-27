"""Dark theme and Serial Cables branding."""

from __future__ import annotations

# Serial Cables brand colors
SC_BLUE = "#1a73e8"
SC_DARK_BG = "#1e1e2e"
SC_CARD_BG = "#2d2d3f"
SC_TEXT = "#e0e0e0"
SC_ACCENT = "#4fc3f7"
SC_SUCCESS = "#66bb6a"
SC_WARNING = "#ffa726"
SC_ERROR = "#ef5350"

# Link status colors
LINK_UP_COLOR = SC_SUCCESS
LINK_DOWN_COLOR = SC_ERROR
LINK_TRAINING_COLOR = SC_WARNING

# PCIe Gen colors
GEN_COLORS = {
    1: "#9e9e9e",
    2: "#42a5f5",
    3: "#66bb6a",
    4: "#ffa726",
    5: "#ef5350",
    6: "#ab47bc",
}


def apply_dark_theme() -> str:
    """Return CSS for dark theme styling."""
    return f"""
    :root {{
        --sc-blue: {SC_BLUE};
        --sc-dark-bg: {SC_DARK_BG};
        --sc-card-bg: {SC_CARD_BG};
        --sc-text: {SC_TEXT};
        --sc-accent: {SC_ACCENT};
    }}
    body {{
        background-color: {SC_DARK_BG} !important;
        color: {SC_TEXT} !important;
    }}
    .q-card {{
        background-color: {SC_CARD_BG} !important;
        color: {SC_TEXT} !important;
    }}
    .q-toolbar {{
        background-color: {SC_BLUE} !important;
    }}
    .q-drawer {{
        background-color: #252538 !important;
    }}
    """
