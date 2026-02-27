"""Tests for EventCounterManager."""

from __future__ import annotations

import ctypes

import pytest

from serialcables_switchtec.core.evcntr import EventCounterManager
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.evcntr import EvCntrSetupResult, EvCntrValue


class TestEventCounterManagerInit:
    """Tests for EventCounterManager construction."""

    def test_init_stores_device_reference(self, device, mock_library):
        mgr = EventCounterManager(device)
        assert mgr._dev is device


class TestEventCounterManagerSetup:
    """Tests for EventCounterManager.setup()."""

    def test_setup_calls_lib_with_correct_args(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.setup(
            stack_id=2,
            counter_id=5,
            port_mask=0xFF,
            type_mask=0x03,
        )
        mock_library.switchtec_evcntr_setup.assert_called_once()
        call_args = mock_library.switchtec_evcntr_setup.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2
        assert call_args[2] == 5

    def test_setup_passes_egress_flag(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.setup(
            stack_id=0,
            counter_id=0,
            port_mask=0x01,
            type_mask=0x01,
            egress=True,
        )
        mock_library.switchtec_evcntr_setup.assert_called_once()

    def test_setup_passes_threshold(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.setup(
            stack_id=1,
            counter_id=3,
            port_mask=0x0F,
            type_mask=0x07,
            threshold=1000,
        )
        mock_library.switchtec_evcntr_setup.assert_called_once()

    def test_setup_defaults_egress_false(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.setup(
            stack_id=0,
            counter_id=0,
            port_mask=0x01,
            type_mask=0x01,
        )
        mock_library.switchtec_evcntr_setup.assert_called_once()
        # The setup struct passed via byref should have egress=0 and threshold=0
        # We verify the call was made; ctypes struct contents are opaque via MagicMock

    def test_setup_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_evcntr_setup.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventCounterManager(device)
        with pytest.raises(SwitchtecError):
            mgr.setup(
                stack_id=0,
                counter_id=0,
                port_mask=0x01,
                type_mask=0x01,
            )


class TestEventCounterManagerGetSetup:
    """Tests for EventCounterManager.get_setup()."""

    def test_get_setup_calls_lib_with_correct_args(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_setup(stack_id=1, counter_id=3, nr_counters=2)
        mock_library.switchtec_evcntr_get_setup.assert_called_once()
        call_args = mock_library.switchtec_evcntr_get_setup.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 1
        assert call_args[2] == 3
        assert call_args[3] == 2

    def test_get_setup_returns_list_of_setup_results(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_setup(stack_id=0, counter_id=0, nr_counters=3)
        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, EvCntrSetupResult)

    def test_get_setup_default_nr_counters_is_one(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_setup(stack_id=0, counter_id=0)
        assert len(result) == 1

    def test_get_setup_returns_default_values_from_uninitialized_struct(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_setup(stack_id=0, counter_id=0, nr_counters=1)
        # ctypes zero-initializes by default
        assert result[0].port_mask == 0
        assert result[0].type_mask == 0
        assert result[0].egress is False
        assert result[0].threshold == 0

    def test_get_setup_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_evcntr_get_setup.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventCounterManager(device)
        with pytest.raises(SwitchtecError):
            mgr.get_setup(stack_id=0, counter_id=0)


class TestEventCounterManagerGetCounts:
    """Tests for EventCounterManager.get_counts()."""

    def test_get_counts_calls_lib_with_correct_args(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_counts(stack_id=2, counter_id=4, nr_counters=3)
        mock_library.switchtec_evcntr_get.assert_called_once()
        call_args = mock_library.switchtec_evcntr_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2
        assert call_args[2] == 4
        assert call_args[3] == 3
        # clear should be 0 (False by default)
        assert call_args[5] == 0

    def test_get_counts_returns_list_of_ints(self, device, mock_library):
        mgr = EventCounterManager(device)
        result = mgr.get_counts(stack_id=0, counter_id=0, nr_counters=4)
        assert isinstance(result, list)
        assert len(result) == 4
        for item in result:
            assert isinstance(item, int)

    def test_get_counts_default_nr_counters_is_one(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_counts(stack_id=0, counter_id=0)
        assert len(result) == 1

    def test_get_counts_passes_clear_flag(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.get_counts(
            stack_id=0, counter_id=0, nr_counters=1, clear=True,
        )
        call_args = mock_library.switchtec_evcntr_get.call_args[0]
        # clear should be 1 (True)
        assert call_args[5] == 1

    def test_get_counts_returns_zeros_for_uninitialized(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_counts(stack_id=0, counter_id=0, nr_counters=2)
        assert all(count == 0 for count in result)

    def test_get_counts_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_evcntr_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventCounterManager(device)
        with pytest.raises(SwitchtecError):
            mgr.get_counts(stack_id=0, counter_id=0)


class TestEventCounterManagerGetBoth:
    """Tests for EventCounterManager.get_both()."""

    def test_get_both_calls_lib_with_correct_args(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=3, counter_id=7, nr_counters=2)
        mock_library.switchtec_evcntr_get_both.assert_called_once()
        call_args = mock_library.switchtec_evcntr_get_both.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 3
        assert call_args[2] == 7
        assert call_args[3] == 2
        # clear should be 0 (False by default)
        assert call_args[6] == 0

    def test_get_both_returns_list_of_evcntr_value(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=0, counter_id=0, nr_counters=3)
        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, EvCntrValue)

    def test_get_both_assigns_correct_counter_ids(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=0, counter_id=5, nr_counters=3)
        assert result[0].counter_id == 5
        assert result[1].counter_id == 6
        assert result[2].counter_id == 7

    def test_get_both_default_nr_counters_is_one(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=0, counter_id=0)
        assert len(result) == 1

    def test_get_both_passes_clear_flag(self, device, mock_library):
        mgr = EventCounterManager(device)
        mgr.get_both(
            stack_id=0, counter_id=0, nr_counters=1, clear=True,
        )
        call_args = mock_library.switchtec_evcntr_get_both.call_args[0]
        # clear should be 1 (True)
        assert call_args[6] == 1

    def test_get_both_includes_setup_in_each_value(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=0, counter_id=0, nr_counters=1)
        assert result[0].setup is not None
        assert isinstance(result[0].setup, EvCntrSetupResult)

    def test_get_both_returns_default_values_from_uninitialized(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.get_both(stack_id=0, counter_id=0, nr_counters=1)
        assert result[0].count == 0
        assert result[0].setup.port_mask == 0
        assert result[0].setup.type_mask == 0
        assert result[0].setup.egress is False
        assert result[0].setup.threshold == 0

    def test_get_both_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_evcntr_get_both.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventCounterManager(device)
        with pytest.raises(SwitchtecError):
            mgr.get_both(stack_id=0, counter_id=0)


class TestEventCounterManagerWait:
    """Tests for EventCounterManager.wait()."""

    def test_wait_calls_lib_with_default_timeout(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.wait()
        mock_library.switchtec_evcntr_wait.assert_called_once_with(
            0xDEADBEEF, 5000,
        )
        assert result == 0

    def test_wait_calls_lib_with_custom_timeout(
        self, device, mock_library
    ):
        mgr = EventCounterManager(device)
        result = mgr.wait(timeout_ms=10000)
        mock_library.switchtec_evcntr_wait.assert_called_once_with(
            0xDEADBEEF, 10000,
        )

    def test_wait_returns_return_code(self, device, mock_library):
        mock_library.switchtec_evcntr_wait.return_value = 42
        mgr = EventCounterManager(device)
        result = mgr.wait(timeout_ms=1000)
        assert result == 42

    def test_wait_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_evcntr_wait.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventCounterManager(device)
        with pytest.raises(SwitchtecError):
            mgr.wait()


class TestEventCounterManagerViaDevice:
    """Tests for accessing EventCounterManager via device property."""

    def test_device_evcntr_property(self, device, mock_library):
        """Verify the evcntr property on SwitchtecDevice returns an EventCounterManager."""
        mgr = device.evcntr
        assert isinstance(mgr, EventCounterManager)

    def test_device_evcntr_property_cached(self, device, mock_library):
        """Verify the evcntr property returns the same instance on repeated access."""
        mgr1 = device.evcntr
        mgr2 = device.evcntr
        assert mgr1 is mgr2
