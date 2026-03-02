"""Tests for UI layout: sidebar navigation groups and routing."""

from __future__ import annotations

from serialcables_switchtec.ui.layout import _NAV_GROUPS, _group_for_path


class TestNavGroups:
    """Tests for sidebar navigation structure."""

    def test_all_groups_have_items(self):
        for category, _icon, items in _NAV_GROUPS:
            assert len(items) > 0, f"Category '{category}' has no items"

    def test_no_duplicate_paths(self):
        paths = [path for _, _, items in _NAV_GROUPS for _, path, _ in items]
        assert len(paths) == len(set(paths)), (
            f"Duplicate paths: {[p for p in paths if paths.count(p) > 1]}"
        )

    def test_no_duplicate_labels(self):
        labels = [label for _, _, items in _NAV_GROUPS for label, _, _ in items]
        assert len(labels) == len(set(labels)), (
            f"Duplicate labels: {[l for l in labels if labels.count(l) > 1]}"
        )

    def test_all_paths_start_with_slash(self):
        for _, _, items in _NAV_GROUPS:
            for label, path, _ in items:
                assert path.startswith("/"), f"'{label}' path missing leading slash: {path}"

    def test_all_items_have_icons(self):
        for _, cat_icon, items in _NAV_GROUPS:
            assert cat_icon, "Category missing icon"
            for label, _, icon in items:
                assert icon, f"'{label}' missing icon"

    def test_expected_categories(self):
        categories = [cat for cat, _, _ in _NAV_GROUPS]
        assert "Device" in categories
        assert "Link Health" in categories
        assert "Signal Integrity" in categories
        assert "Fabric" in categories

    def test_discovery_in_device_group(self):
        assert _group_for_path("/") == "Device"

    def test_eye_diagram_in_signal_integrity(self):
        assert _group_for_path("/eye") == "Signal Integrity"

    def test_margin_testing_in_signal_integrity(self):
        assert _group_for_path("/margin") == "Signal Integrity"

    def test_fabric_view_in_fabric(self):
        assert _group_for_path("/fabric-view") == "Fabric"

    def test_unknown_path_returns_none(self):
        assert _group_for_path("/nonexistent") is None

    def test_total_page_count(self):
        total = sum(len(items) for _, _, items in _NAV_GROUPS)
        assert total == 18, f"Expected 18 pages, got {total}"
