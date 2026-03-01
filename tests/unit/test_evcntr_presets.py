"""Tests for event counter preset definitions and lookup functions."""

from __future__ import annotations

import dataclasses

import pytest

from serialcables_switchtec.core.evcntr_presets import (
    EventCounterPreset,
    PRESETS,
    get_preset,
    list_presets,
)


class TestPresetsDict:
    """Tests for the PRESETS dictionary structure."""

    def test_presets_dict_has_10_entries(self):
        assert len(PRESETS) == 10

    def test_presets_expected_keys(self):
        expected = {
            "data_integrity",
            "link_errors",
            "ber_relevant",
            "thermal",
            "power",
            "completion",
            "acs_violation",
            "flow_control",
            "surprise_events",
            "all_errors",
        }
        assert set(PRESETS.keys()) == expected

    def test_each_preset_has_nonzero_mask(self):
        for name, preset in PRESETS.items():
            assert preset.type_mask > 0, f"Preset {name!r} has zero type_mask"

    def test_each_preset_has_display_name(self):
        for name, preset in PRESETS.items():
            assert preset.display_name, f"Preset {name!r} has empty display_name"

    def test_presets_have_unique_names(self):
        names = [preset.name for preset in PRESETS.values()]
        assert len(names) == len(set(names)), "Preset names are not unique"


class TestAllErrorsPreset:
    """Tests for the all_errors preset specifically."""

    def test_all_error_preset_mask(self):
        # ALL_ERRORS = (1 << 19) - 1 = 0x7FFFF (bits 0-18, 19 error types)
        assert PRESETS["all_errors"].type_mask == (1 << 19) - 1

    def test_all_error_preset_threshold_zero(self):
        assert PRESETS["all_errors"].threshold == 0


class TestGetPreset:
    """Tests for the get_preset() lookup function."""

    def test_get_preset_valid_name(self):
        preset = get_preset("link_errors")
        assert isinstance(preset, EventCounterPreset)
        assert preset.name == "link_errors"

    def test_get_preset_invalid_name_raises(self):
        with pytest.raises(KeyError):
            get_preset("nonexistent")


class TestListPresets:
    """Tests for the list_presets() function."""

    def test_list_presets_returns_all(self):
        result = list_presets()
        assert len(result) == len(PRESETS)

    def test_list_presets_returns_preset_instances(self):
        result = list_presets()
        for item in result:
            assert isinstance(item, EventCounterPreset)


class TestEventCounterPresetFrozen:
    """Tests for the frozen dataclass behavior."""

    def test_preset_is_frozen(self):
        preset = get_preset("link_errors")
        with pytest.raises(dataclasses.FrozenInstanceError):
            preset.name = "mutated"

    def test_preset_has_expected_fields(self):
        preset = get_preset("data_integrity")
        assert hasattr(preset, "name")
        assert hasattr(preset, "display_name")
        assert hasattr(preset, "description")
        assert hasattr(preset, "type_mask")
        assert hasattr(preset, "threshold")
