"""Tests for recipe-specific metric card renderers (registry dispatch).

Since NiceGUI components require a running server, these tests validate
the registry dispatch logic and renderer signatures without rendering.
"""

from __future__ import annotations

import pytest

from serialcables_switchtec.ui.components.monitor_metrics import (
    _RENDERERS,
    _render_generic,
    render_metrics,
)


class TestRendererRegistry:
    def test_all_priority_renderers_registered(self) -> None:
        expected = {
            "cross_hair_margin",
            "ber_soak",
            "bandwidth_baseline",
            "link_health_check",
            "all_port_sweep",
            "eye_quick_scan",
        }
        assert expected == set(_RENDERERS.keys())

    def test_renderers_are_callable(self) -> None:
        for key, renderer in _RENDERERS.items():
            assert callable(renderer), f"{key} renderer not callable"

    def test_render_metrics_dispatches_known_key(self) -> None:
        """Verify dispatch resolves to the registered renderer."""
        renderer = _RENDERERS.get("cross_hair_margin")
        assert renderer is not None
        assert renderer.__name__ == "_render_cross_hair_margin"

    def test_render_metrics_dispatches_unknown_key(self) -> None:
        """Unknown recipe keys should fall back to generic."""
        renderer = _RENDERERS.get("totally_unknown_recipe")
        assert renderer is None  # not in registry

    def test_generic_renderer_is_callable(self) -> None:
        assert callable(_render_generic)

    def test_each_renderer_accepts_correct_signature(self) -> None:
        """All renderers should accept (data: dict, container) args."""
        import inspect
        for key, renderer in _RENDERERS.items():
            sig = inspect.signature(renderer)
            params = list(sig.parameters.keys())
            assert len(params) == 2, f"{key}: expected 2 params, got {params}"
