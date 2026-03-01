"""Shared page scaffold with header and sidebar navigation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS, apply_dark_theme, gen_color

# Grouped navigation: (category_label, category_icon, items)
# Each item: (label, path, icon)
_NAV_GROUPS: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    (
        "Device",
        "memory",
        [
            ("Discovery", "/", "search"),
            ("Dashboard", "/dashboard", "dashboard"),
            ("Firmware", "/firmware", "system_update"),
        ],
    ),
    (
        "Link Health",
        "link",
        [
            ("Ports", "/ports", "device_hub"),
            ("LTSSM Trace", "/ltssm", "timeline"),
            ("Events", "/events", "notifications"),
            ("Event Counters", "/evcntr", "bar_chart"),
        ],
    ),
    (
        "Signal Integrity",
        "ssid_chart",
        [
            ("Eye Diagram", "/eye", "visibility"),
            ("BER Testing", "/ber", "science"),
            ("Equalization", "/equalization", "tune"),
            ("Margin Testing", "/margin", "straighten"),
            ("OSA", "/osa", "analytics"),
        ],
    ),
    (
        "Performance & Debug",
        "speed",
        [
            ("Performance", "/performance", "speed"),
            ("Error Injection", "/injection", "warning"),
        ],
    ),
    (
        "Fabric",
        "hub",
        [
            ("Fabric", "/fabric", "hub"),
            ("Fabric View", "/fabric-view", "account_tree"),
        ],
    ),
    (
        "Automation",
        "play_circle",
        [
            ("Workflows", "/workflows", "play_circle"),
        ],
    ),
]


def _group_for_path(path: str) -> str | None:
    """Return the category label that contains *path*, or ``None``."""
    for category, _icon, items in _NAV_GROUPS:
        if any(p == path for _, p, _ in items):
            return category
    return None


@contextmanager
def page_layout(
    title: str = "Dashboard",
    current_path: str = "/",
) -> Generator[None, None, None]:
    """Shared page layout with header, sidebar, and content area.

    Args:
        title: Page title displayed in the header.
        current_path: URL path of the current page for nav highlighting.
    """
    from serialcables_switchtec.ui import state

    ui.page_title(f"Athena - {title}")
    ui.add_css(apply_dark_theme())
    ui.add_css(_sidebar_css())

    # --- Header ---
    with ui.header(elevated=True).classes("q-pa-sm"):
        with ui.row().classes("w-full items-center no-wrap q-gutter-md"):
            ui.image("/static/logo.png").style(
                "width: 32px; height: 32px;"
            )
            ui.label("ATHENA").classes("text-h6 text-bold").style(
                f"color: {COLORS.accent}; letter-spacing: 0.15em;"
            )
            ui.label("|").style(f"color: {COLORS.text_muted};")
            ui.label("Serial Cables Switchtec Switch Manager").classes(
                "text-subtitle2"
            ).style(f"color: {COLORS.text_secondary};")

            ui.space()

            # Device context in header (uses cached summary, no I/O)
            if state.is_connected():
                summary = state.get_summary()
                if summary:
                    color = gen_color(summary.generation)
                    ui.icon("memory").style(f"color: {color};")
                    ui.label(summary.name).classes("text-subtitle2").style(
                        f"color: {COLORS.text_primary};"
                    )
                    ui.badge(summary.generation).style(
                        f"background-color: {color};"
                    )
                    ui.label(f"{summary.die_temperature:.0f}\u00b0C").classes(
                        "text-caption"
                    ).style(f"color: {COLORS.text_secondary};")
                    ui.button(
                        icon="link_off",
                        on_click=_on_disconnect,
                    ).props("flat dense round size=sm").tooltip("Disconnect")
            else:
                ui.label("No device").classes("text-caption").style(
                    f"color: {COLORS.text_muted};"
                )

            ui.label(title).classes("text-subtitle1").style(
                f"color: {COLORS.text_primary};"
            )

    # --- Sidebar navigation ---
    active_group = _group_for_path(current_path)

    with ui.left_drawer(value=True).classes("q-pa-none athena-sidebar"):
        ui.label("Navigation").classes("text-h6 q-mb-sm q-px-md q-pt-md").style(
            f"color: {COLORS.text_primary};"
        )

        for category, cat_icon, items in _NAV_GROUPS:
            is_open = category == active_group
            has_active = any(p == current_path for _, p, _ in items)

            # Category header color: accent if it contains the active page
            cat_color = COLORS.accent if has_active else COLORS.text_secondary

            with ui.expansion(
                text=category,
                icon=cat_icon,
                value=is_open,
            ).classes("athena-nav-group").props("dense") as exp:
                exp.style(f"color: {cat_color};")

                for label, path, icon in items:
                    _nav_item(label, path, icon, is_active=path == current_path)

    with ui.column().classes("w-full q-pa-md"):
        yield


def _nav_item(label: str, path: str, icon: str, *, is_active: bool) -> None:
    """Render a single sidebar navigation item."""
    bg = f"background-color: {COLORS.bg_card};" if is_active else ""
    border = (
        f"border-left: 3px solid {COLORS.accent}; padding-left: 8px;"
        if is_active
        else "border-left: 3px solid transparent; padding-left: 8px;"
    )
    font_weight = "font-weight: 600;" if is_active else ""
    color = COLORS.accent if is_active else COLORS.text_secondary

    with ui.row().classes("items-center q-mb-xs q-pa-xs").style(
        f"{bg}{border} border-radius: 4px; cursor: pointer; {font_weight}"
    ).on("click", lambda _, p=path: ui.navigate.to(p)):
        ui.icon(icon).style(f"color: {color}; font-size: 1.1em;")
        ui.label(label).style(
            f"color: {color}; text-decoration: none; font-size: 0.85em;"
        )


def _sidebar_css() -> str:
    """CSS overrides for the collapsible sidebar navigation."""
    return f"""
    .athena-sidebar .q-expansion-item {{
        border-bottom: 1px solid {COLORS.text_muted};
    }}
    .athena-sidebar .q-expansion-item__container {{
        padding: 0;
    }}
    .athena-sidebar .q-item {{
        min-height: 36px;
        padding: 4px 16px;
    }}
    .athena-sidebar .q-item__section--avatar {{
        min-width: 28px;
        padding-right: 8px;
    }}
    .athena-sidebar .q-item__label {{
        font-size: 0.85em;
        font-weight: 500;
        letter-spacing: 0.03em;
    }}
    .athena-sidebar .q-expansion-item__content {{
        padding: 0 8px 8px 8px;
    }}
    """


def _on_disconnect() -> None:
    """Disconnect from the active device and navigate to discovery."""
    from serialcables_switchtec.ui import state

    state.disconnect_device()
    ui.notify("Disconnected", type="info", position="top")
    ui.navigate.to("/")
