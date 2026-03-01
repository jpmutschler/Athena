"""Dark theme and Serial Cables branding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """Centralized color palette for Athena dashboard."""

    # Accent colors
    accent: str = "#39d353"
    blue: str = "#58a6ff"
    purple: str = "#bc8cff"

    # Text layers
    text_primary: str = "#e6edf3"
    text_secondary: str = "#8b949e"
    text_muted: str = "#484f58"

    # Background layers
    bg_primary: str = "#0d1117"
    bg_secondary: str = "#161b22"
    bg_card: str = "#1c2128"

    # Status colors
    success: str = "#66bb6a"
    warning: str = "#ffa726"
    error: str = "#ef5350"


COLORS = Colors()

# Link status colors
LINK_UP_COLOR = COLORS.success
LINK_DOWN_COLOR = COLORS.error
LINK_TRAINING_COLOR = COLORS.warning

# PCIe Gen colors
GEN_COLORS = {
    1: "#9e9e9e",
    2: "#42a5f5",
    3: "#66bb6a",
    4: "#ffa726",
    5: "#ef5350",
    6: "#ab47bc",
}


def gen_number(gen_str: str) -> int:
    """Extract generation number from string like 'GEN4'."""
    if gen_str and gen_str[-1].isdigit():
        return int(gen_str[-1])
    return 0


def gen_color(gen_str: str) -> str:
    """Return the color for a PCIe generation string."""
    return GEN_COLORS.get(gen_number(gen_str), "#9e9e9e")


def plotly_layout_defaults() -> dict:
    """Standard dark theme layout for Plotly charts.

    Returns a dict of layout properties that align Plotly charts with the
    Athena dashboard dark theme.  Callers can merge additional keys via
    ``{**plotly_layout_defaults(), "title": "My Chart"}``.
    """
    return {
        "plot_bgcolor": COLORS.bg_card,
        "paper_bgcolor": COLORS.bg_primary,
        "font": {"color": COLORS.text_primary, "family": "JetBrains Mono"},
        "xaxis": {"gridcolor": COLORS.text_muted, "zerolinecolor": COLORS.text_muted},
        "yaxis": {"gridcolor": COLORS.text_muted, "zerolinecolor": COLORS.text_muted},
        "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
    }


def apply_dark_theme() -> str:
    """Return CSS for dark theme styling."""
    return f"""
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
    :root {{
        --sc-accent: {COLORS.accent};
        --sc-bg-primary: {COLORS.bg_primary};
        --sc-bg-secondary: {COLORS.bg_secondary};
        --sc-bg-card: {COLORS.bg_card};
        --sc-text-primary: {COLORS.text_primary};
        --sc-text-secondary: {COLORS.text_secondary};
    }}
    body {{
        background-color: {COLORS.bg_primary} !important;
        color: {COLORS.text_primary} !important;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .q-card {{
        background-color: {COLORS.bg_card} !important;
        color: {COLORS.text_primary} !important;
    }}
    .q-header {{
        background-color: {COLORS.bg_secondary} !important;
        border-bottom: 1px solid {COLORS.text_muted} !important;
    }}
    .q-drawer {{
        background-color: {COLORS.bg_secondary} !important;
        border-right: 1px solid {COLORS.text_muted} !important;
    }}
    .q-table {{
        background-color: {COLORS.bg_card} !important;
        color: {COLORS.text_primary} !important;
    }}
    """
