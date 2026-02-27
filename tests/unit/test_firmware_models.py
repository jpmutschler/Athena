"""Tests for firmware Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from serialcables_switchtec.models.firmware import FwImageInfo


def _make_fw_image_info(**overrides) -> FwImageInfo:
    """Create a FwImageInfo with sensible defaults, allowing overrides."""
    defaults = {
        "generation": "GEN4",
        "partition_type": "BL2",
        "version": "4.40",
        "partition_addr": 0x1000,
        "partition_len": 0x10000,
        "image_len": 0x8000,
        "valid": True,
        "active": True,
        "running": True,
        "read_only": False,
    }
    defaults.update(overrides)
    return FwImageInfo(**defaults)


class TestFwImageInfo:
    def test_creation(self) -> None:
        info = _make_fw_image_info()
        assert info.generation == "GEN4"
        assert info.partition_type == "BL2"
        assert info.version == "4.40"
        assert info.partition_addr == 0x1000
        assert info.partition_len == 0x10000
        assert info.image_len == 0x8000
        assert info.valid is True
        assert info.active is True
        assert info.running is True
        assert info.read_only is False

    def test_frozen_prevents_mutation(self) -> None:
        info = _make_fw_image_info()
        with pytest.raises(ValidationError):
            info.generation = "GEN5"

    def test_frozen_prevents_mutation_on_bool(self) -> None:
        info = _make_fw_image_info()
        with pytest.raises(ValidationError):
            info.valid = False

    def test_frozen_prevents_mutation_on_int(self) -> None:
        info = _make_fw_image_info()
        with pytest.raises(ValidationError):
            info.partition_addr = 0x2000

    def test_all_fields_accessible(self) -> None:
        """Verify every declared field is present and accessible."""
        expected_fields = {
            "generation", "partition_type", "version",
            "partition_addr", "partition_len", "image_len",
            "valid", "active", "running", "read_only",
        }
        assert set(FwImageInfo.model_fields.keys()) == expected_fields

    def test_different_generations(self) -> None:
        for gen in ("GEN3", "GEN4", "GEN5", "GEN6"):
            info = _make_fw_image_info(generation=gen)
            assert info.generation == gen

    def test_different_partition_types(self) -> None:
        for part_type in ("BL2", "IMG", "CFG", "MAP", "KEY"):
            info = _make_fw_image_info(partition_type=part_type)
            assert info.partition_type == part_type

    def test_inactive_image(self) -> None:
        info = _make_fw_image_info(
            valid=False, active=False, running=False, read_only=True,
        )
        assert info.valid is False
        assert info.active is False
        assert info.running is False
        assert info.read_only is True

    def test_zero_lengths(self) -> None:
        info = _make_fw_image_info(
            partition_addr=0, partition_len=0, image_len=0,
        )
        assert info.partition_addr == 0
        assert info.partition_len == 0
        assert info.image_len == 0

    def test_large_addresses(self) -> None:
        info = _make_fw_image_info(
            partition_addr=0xFFFFFFFF,
            partition_len=0x1000000,
            image_len=0x800000,
        )
        assert info.partition_addr == 0xFFFFFFFF
        assert info.partition_len == 0x1000000

    def test_model_dump(self) -> None:
        """Verify serialization to dict works correctly."""
        info = _make_fw_image_info()
        data = info.model_dump()
        assert isinstance(data, dict)
        assert data["generation"] == "GEN4"
        assert data["partition_addr"] == 0x1000
        assert data["valid"] is True

    def test_equality(self) -> None:
        """Two instances with same data should be equal."""
        info1 = _make_fw_image_info()
        info2 = _make_fw_image_info()
        assert info1 == info2

    def test_inequality(self) -> None:
        info1 = _make_fw_image_info(version="4.40")
        info2 = _make_fw_image_info(version="5.00")
        assert info1 != info2

    def test_missing_required_field_raises(self) -> None:
        """Omitting a required field should raise ValidationError."""
        with pytest.raises(ValidationError):
            FwImageInfo(
                generation="GEN4",
                partition_type="BL2",
                # version omitted
                partition_addr=0x1000,
                partition_len=0x10000,
                image_len=0x8000,
                valid=True,
                active=True,
                running=True,
                read_only=False,
            )
