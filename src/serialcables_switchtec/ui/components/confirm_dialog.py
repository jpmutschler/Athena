"""Reusable async confirmation dialog component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS


async def confirm_action(
    title: str,
    message: str,
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    *,
    dangerous: bool = False,
) -> bool:
    """Show a confirmation dialog and return True if confirmed.

    The dialog blocks the calling coroutine until the user clicks
    Confirm or Cancel.

    Args:
        title: Dialog title text.
        message: Body message describing the action.
        confirm_text: Label for the confirmation button.
        cancel_text: Label for the cancel button.
        dangerous: If True, render the confirm button in error/red color
            to signal a destructive operation (e.g. Hard Reset, Error
            Injection, CSR Write).

    Returns:
        True if the user clicked Confirm, False otherwise.
    """
    with ui.dialog() as dialog, ui.card().style(
        f"background-color: {COLORS.bg_card}; min-width: 350px;"
    ):
        ui.label(title).classes("text-h6").style(
            f"color: {COLORS.text_primary};"
        )
        ui.label(message).classes("q-mt-sm").style(
            f"color: {COLORS.text_secondary};"
        )

        with ui.row().classes("w-full justify-end q-mt-md q-gutter-sm"):
            ui.button(
                cancel_text,
                on_click=lambda: dialog.submit(False),
            ).props("flat").style(f"color: {COLORS.text_secondary};")

            confirm_color = COLORS.error if dangerous else COLORS.accent
            ui.button(
                confirm_text,
                on_click=lambda: dialog.submit(True),
            ).props("unelevated").style(
                f"background-color: {confirm_color}; color: {COLORS.bg_primary};"
            )

    result = await dialog
    return bool(result)
