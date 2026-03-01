"""Tests for UI theme module: colors, gen helpers, layout defaults, CSS."""

from __future__ import annotations

import pytest

from serialcables_switchtec.ui.theme import (
    COLORS,
    GEN_COLORS,
    LINK_DOWN_COLOR,
    LINK_TRAINING_COLOR,
    LINK_UP_COLOR,
    Colors,
    apply_dark_theme,
    gen_color,
    gen_number,
    plotly_layout_defaults,
)


# ── Colors frozen dataclass ──────────────────────────────────────────────


class TestColors:
    """Colors dataclass tests."""

    def test_colors_is_frozen(self):
        with pytest.raises(AttributeError):
            COLORS.accent = "#000000"  # type: ignore[misc]

    def test_accent_color(self):
        assert COLORS.accent == "#39d353"

    def test_blue_color(self):
        assert COLORS.blue == "#58a6ff"

    def test_purple_color(self):
        assert COLORS.purple == "#bc8cff"

    def test_text_primary(self):
        assert COLORS.text_primary == "#e6edf3"

    def test_text_secondary(self):
        assert COLORS.text_secondary == "#8b949e"

    def test_text_muted(self):
        assert COLORS.text_muted == "#484f58"

    def test_bg_primary(self):
        assert COLORS.bg_primary == "#0d1117"

    def test_bg_secondary(self):
        assert COLORS.bg_secondary == "#161b22"

    def test_bg_card(self):
        assert COLORS.bg_card == "#1c2128"

    def test_success_color(self):
        assert COLORS.success == "#66bb6a"

    def test_warning_color(self):
        assert COLORS.warning == "#ffa726"

    def test_error_color(self):
        assert COLORS.error == "#ef5350"

    def test_default_construction(self):
        c = Colors()
        assert c.accent == "#39d353"

    def test_custom_construction(self):
        c = Colors(accent="#ffffff")
        assert c.accent == "#ffffff"

    def test_link_up_color(self):
        assert LINK_UP_COLOR == COLORS.success

    def test_link_down_color(self):
        assert LINK_DOWN_COLOR == COLORS.error

    def test_link_training_color(self):
        assert LINK_TRAINING_COLOR == COLORS.warning


# ── GEN_COLORS dict ─────────────────────────────────────────────────────


class TestGenColors:
    """GEN_COLORS dict tests."""

    def test_gen1_color(self):
        assert GEN_COLORS[1] == "#9e9e9e"

    def test_gen2_color(self):
        assert GEN_COLORS[2] == "#42a5f5"

    def test_gen3_color(self):
        assert GEN_COLORS[3] == "#66bb6a"

    def test_gen4_color(self):
        assert GEN_COLORS[4] == "#ffa726"

    def test_gen5_color(self):
        assert GEN_COLORS[5] == "#ef5350"

    def test_gen6_color(self):
        assert GEN_COLORS[6] == "#ab47bc"

    def test_all_gens_present(self):
        assert set(GEN_COLORS.keys()) == {1, 2, 3, 4, 5, 6}


# ── gen_number() ─────────────────────────────────────────────────────────


class TestGenNumber:
    """gen_number() extraction tests."""

    @pytest.mark.parametrize(
        "gen_str, expected",
        [
            ("GEN1", 1),
            ("GEN2", 2),
            ("GEN3", 3),
            ("GEN4", 4),
            ("GEN5", 5),
            ("GEN6", 6),
            ("Gen4", 4),
            ("gen5", 5),
        ],
    )
    def test_valid_gen_strings(self, gen_str, expected):
        assert gen_number(gen_str) == expected

    def test_empty_string(self):
        assert gen_number("") == 0

    def test_no_digit(self):
        assert gen_number("GEN") == 0

    def test_non_digit_suffix(self):
        assert gen_number("GENX") == 0


# ── gen_color() ──────────────────────────────────────────────────────────


class TestGenColor:
    """gen_color() lookup tests."""

    @pytest.mark.parametrize("gen", range(1, 7))
    def test_valid_gen(self, gen):
        color = gen_color(f"GEN{gen}")
        assert color == GEN_COLORS[gen]

    def test_unknown_gen_returns_gray(self):
        assert gen_color("GEN9") == "#9e9e9e"

    def test_empty_string_returns_gray(self):
        assert gen_color("") == "#9e9e9e"


# ── plotly_layout_defaults() ─────────────────────────────────────────────


class TestPlotlyLayoutDefaults:
    """plotly_layout_defaults() tests."""

    def test_returns_dict(self):
        result = plotly_layout_defaults()
        assert isinstance(result, dict)

    def test_has_plot_bgcolor(self):
        assert plotly_layout_defaults()["plot_bgcolor"] == COLORS.bg_card

    def test_has_paper_bgcolor(self):
        assert plotly_layout_defaults()["paper_bgcolor"] == COLORS.bg_primary

    def test_has_font(self):
        font = plotly_layout_defaults()["font"]
        assert font["color"] == COLORS.text_primary
        assert "JetBrains Mono" in font["family"]

    def test_has_xaxis(self):
        xaxis = plotly_layout_defaults()["xaxis"]
        assert "gridcolor" in xaxis
        assert "zerolinecolor" in xaxis

    def test_has_yaxis(self):
        yaxis = plotly_layout_defaults()["yaxis"]
        assert "gridcolor" in yaxis
        assert "zerolinecolor" in yaxis

    def test_has_margin(self):
        margin = plotly_layout_defaults()["margin"]
        assert all(k in margin for k in ("l", "r", "t", "b"))

    def test_merge_with_additional_keys(self):
        merged = {**plotly_layout_defaults(), "title": "My Chart"}
        assert merged["title"] == "My Chart"
        assert "plot_bgcolor" in merged


# ── apply_dark_theme() ───────────────────────────────────────────────────


class TestApplyDarkTheme:
    """apply_dark_theme() CSS tests."""

    def test_returns_string(self):
        css = apply_dark_theme()
        assert isinstance(css, str)

    def test_contains_root_vars(self):
        css = apply_dark_theme()
        assert "--sc-accent" in css
        assert "--sc-bg-primary" in css

    def test_contains_body_styles(self):
        css = apply_dark_theme()
        assert "body" in css
        assert COLORS.bg_primary in css

    def test_contains_card_styles(self):
        css = apply_dark_theme()
        assert ".q-card" in css
        assert COLORS.bg_card in css

    def test_contains_header_styles(self):
        css = apply_dark_theme()
        assert ".q-header" in css

    def test_contains_drawer_styles(self):
        css = apply_dark_theme()
        assert ".q-drawer" in css

    def test_contains_table_styles(self):
        css = apply_dark_theme()
        assert ".q-table" in css

    def test_contains_font_import(self):
        css = apply_dark_theme()
        assert "JetBrains Mono" in css
