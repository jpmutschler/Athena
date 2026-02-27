"""Switchtec device management: open, close, status, properties."""

from __future__ import annotations

import ctypes
import threading
from ctypes import POINTER, c_float, c_int
from typing import TYPE_CHECKING, Self

from serialcables_switchtec.bindings.constants import (
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
)
from serialcables_switchtec.bindings.functions import setup_prototypes
from serialcables_switchtec.bindings.library import get_library, load_library
from serialcables_switchtec.bindings.types import SwitchtecDeviceInfo, SwitchtecStatus
from serialcables_switchtec.exceptions import (
    DeviceOpenError,
    SwitchtecError,
    check_error,
    check_null,
)
from serialcables_switchtec.models.device import (
    DeviceInfo,
    DeviceSummary,
    PortId,
    PortStatus,
)
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.diagnostics import DiagnosticsManager
    from serialcables_switchtec.core.evcntr import EventCounterManager
    from serialcables_switchtec.core.events import EventManager
    from serialcables_switchtec.core.fabric import FabricManager
    from serialcables_switchtec.core.firmware import FirmwareManager
    from serialcables_switchtec.core.osa import OrderedSetAnalyzer
    from serialcables_switchtec.core.performance import PerformanceManager

logger = get_logger(__name__)

_GEN_NAMES = {
    SwitchtecGen.GEN3: "GEN3",
    SwitchtecGen.GEN4: "GEN4",
    SwitchtecGen.GEN5: "GEN5",
    SwitchtecGen.GEN6: "GEN6",
    SwitchtecGen.UNKNOWN: "Unknown",
}

_VARIANT_NAMES = {
    SwitchtecVariant.PFX: "PFX",
    SwitchtecVariant.PFXL: "PFX-L",
    SwitchtecVariant.PFXI: "PFX-I",
    SwitchtecVariant.PSX: "PSX",
    SwitchtecVariant.PAX: "PAX",
    SwitchtecVariant.PAXA: "PAX-A",
    SwitchtecVariant.PFXA: "PFX-A",
    SwitchtecVariant.PSXA: "PSX-A",
    SwitchtecVariant.UNKNOWN: "Unknown",
}

_PHASE_NAMES = {
    SwitchtecBootPhase.BL1: "BL1",
    SwitchtecBootPhase.BL2: "BL2",
    SwitchtecBootPhase.FW: "Main Firmware",
    SwitchtecBootPhase.UNKNOWN: "Unknown Phase",
}


_prototypes_configured = False
_lib_init_lock = threading.Lock()


def _ensure_library() -> ctypes.CDLL:
    """Load and configure the library if not already done."""
    global _prototypes_configured
    with _lib_init_lock:
        lib = load_library()
        if not _prototypes_configured:
            setup_prototypes(lib)
            _prototypes_configured = True
        return lib


class SwitchtecDevice:
    """Manages a connection to a single Switchtec device.

    Use as a context manager for automatic cleanup:

        with SwitchtecDevice.open("/dev/switchtec0") as dev:
            print(dev.die_temperature)
    """

    def __init__(self, handle: int, lib: ctypes.CDLL) -> None:
        self._handle = handle
        self._lib = lib
        self._closed = False
        self._diagnostics_mgr: DiagnosticsManager | None = None
        self._evcntr_mgr: EventCounterManager | None = None
        self._events_mgr: EventManager | None = None
        self._fabric_mgr: FabricManager | None = None
        self._firmware_mgr: FirmwareManager | None = None
        self._osa_mgr: OrderedSetAnalyzer | None = None
        self._performance_mgr: PerformanceManager | None = None

    @classmethod
    def open(cls, device: str) -> SwitchtecDevice:
        """Open a Switchtec device by name or path.

        Args:
            device: Device path (e.g., "/dev/switchtec0" on Linux,
                    "\\\\.\\switchtec0" on Windows).

        Returns:
            A new SwitchtecDevice instance.

        Raises:
            DeviceOpenError: If the device cannot be opened.
        """
        lib = _ensure_library()
        handle = lib.switchtec_open(device.encode())
        check_null(handle, f"open device: {device}")
        logger.info("device_opened", device=device)
        return cls(handle, lib)

    @classmethod
    def open_by_index(cls, index: int) -> SwitchtecDevice:
        """Open a Switchtec device by its enumeration index."""
        lib = _ensure_library()
        handle = lib.switchtec_open_by_index(index)
        check_null(handle, f"open device at index {index}")
        logger.info("device_opened", index=index)
        return cls(handle, lib)

    @classmethod
    def open_by_pci_addr(
        cls, domain: int, bus: int, device: int, func: int
    ) -> SwitchtecDevice:
        """Open a Switchtec device by PCI address."""
        lib = _ensure_library()
        handle = lib.switchtec_open_by_pci_addr(domain, bus, device, func)
        check_null(handle, f"open device at {domain:04x}:{bus:02x}:{device:02x}.{func}")
        return cls(handle, lib)

    def close(self) -> None:
        """Close the device handle."""
        if not self._closed and self._handle:
            self._lib.switchtec_close(self._handle)
            self._closed = True
            logger.info("device_closed")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @property
    def handle(self) -> int:
        """Raw device handle for direct library calls."""
        if self._closed:
            raise SwitchtecError("Device is closed")
        return self._handle

    @property
    def lib(self) -> ctypes.CDLL:
        """Library handle for sub-managers."""
        return self._lib

    @property
    def diagnostics(self) -> DiagnosticsManager:
        """Access diagnostics operations."""
        if self._diagnostics_mgr is None:
            from serialcables_switchtec.core.diagnostics import DiagnosticsManager

            self._diagnostics_mgr = DiagnosticsManager(self)
        return self._diagnostics_mgr

    @property
    def evcntr(self) -> EventCounterManager:
        """Access event counter operations."""
        if self._evcntr_mgr is None:
            from serialcables_switchtec.core.evcntr import EventCounterManager

            self._evcntr_mgr = EventCounterManager(self)
        return self._evcntr_mgr

    @property
    def events(self) -> EventManager:
        """Access event management operations."""
        if self._events_mgr is None:
            from serialcables_switchtec.core.events import EventManager

            self._events_mgr = EventManager(self)
        return self._events_mgr

    @property
    def firmware(self) -> FirmwareManager:
        """Access firmware management operations."""
        if self._firmware_mgr is None:
            from serialcables_switchtec.core.firmware import FirmwareManager

            self._firmware_mgr = FirmwareManager(self)
        return self._firmware_mgr

    @property
    def fabric(self) -> FabricManager:
        """Access fabric/topology operations (PAX devices only)."""
        if self._fabric_mgr is None:
            from serialcables_switchtec.core.fabric import FabricManager

            self._fabric_mgr = FabricManager(self)
        return self._fabric_mgr

    @property
    def osa(self) -> OrderedSetAnalyzer:
        """Access Ordered Set Analyzer operations."""
        if self._osa_mgr is None:
            from serialcables_switchtec.core.osa import OrderedSetAnalyzer

            self._osa_mgr = OrderedSetAnalyzer(self)
        return self._osa_mgr

    @property
    def performance(self) -> PerformanceManager:
        """Access performance monitoring operations."""
        if self._performance_mgr is None:
            from serialcables_switchtec.core.performance import PerformanceManager

            self._performance_mgr = PerformanceManager(self)
        return self._performance_mgr

    @property
    def name(self) -> str:
        """Device name."""
        result = self._lib.switchtec_name(self.handle)
        return result.decode() if result else ""

    @property
    def partition(self) -> int:
        """Current partition number."""
        return self._lib.switchtec_partition(self.handle)

    @property
    def device_id(self) -> int:
        """PCI device ID."""
        return self._lib.switchtec_device_id(self.handle)

    @property
    def generation(self) -> SwitchtecGen:
        """PCIe generation."""
        return SwitchtecGen(self._lib.switchtec_gen(self.handle))

    @property
    def generation_str(self) -> str:
        """PCIe generation as a string."""
        return _GEN_NAMES.get(self.generation, "Unknown")

    @property
    def variant(self) -> SwitchtecVariant:
        """Device variant (PFX, PSX, PAX, etc.)."""
        return SwitchtecVariant(self._lib.switchtec_variant(self.handle))

    @property
    def variant_str(self) -> str:
        """Device variant as a string."""
        return _VARIANT_NAMES.get(self.variant, "Unknown")

    @property
    def boot_phase(self) -> SwitchtecBootPhase:
        """Current boot phase."""
        return SwitchtecBootPhase(self._lib.switchtec_boot_phase(self.handle))

    @property
    def boot_phase_str(self) -> str:
        """Boot phase as a string."""
        return _PHASE_NAMES.get(self.boot_phase, "Unknown Phase")

    @property
    def die_temperature(self) -> float:
        """Die temperature in degrees Celsius."""
        return self._lib.switchtec_die_temp(self.handle)

    def get_die_temperatures(self, nr_sensors: int = 5) -> list[float]:
        """Get temperature readings from multiple sensors.

        Args:
            nr_sensors: Number of sensors to read.

        Returns:
            List of temperature readings in degrees Celsius.
        """
        readings = (c_float * nr_sensors)()
        ret = self._lib.switchtec_die_temps(self.handle, nr_sensors, readings)
        check_error(ret, "die_temps")
        return [readings[i] for i in range(nr_sensors)]

    def get_fw_version(self) -> str:
        """Get firmware version string."""
        buf = ctypes.create_string_buffer(256)
        ret = self._lib.switchtec_get_fw_version(self.handle, buf, 256)
        check_error(ret, "get_fw_version")
        return buf.value.decode()

    def get_status(self) -> list[PortStatus]:
        """Get status of all ports.

        Returns:
            List of PortStatus for each port.
        """
        status_ptr = POINTER(SwitchtecStatus)()
        nr_ports = self._lib.switchtec_status(
            self.handle, ctypes.byref(status_ptr)
        )
        check_error(nr_ports, "status")

        try:
            # Populate device info (Linux only)
            self._lib.switchtec_get_devices(
                self.handle, status_ptr, nr_ports
            )

            results: list[PortStatus] = []
            for i in range(nr_ports):
                s = status_ptr[i]
                port_id = PortId(
                    partition=s.port.partition,
                    stack=s.port.stack,
                    upstream=bool(s.port.upstream),
                    stk_id=s.port.stk_id,
                    phys_id=s.port.phys_id,
                    log_id=s.port.log_id,
                )

                ltssm_str_val = ""
                if s.ltssm_str:
                    ltssm_str_val = s.ltssm_str.decode()

                lane_rev_str = ""
                if s.lane_reversal_str:
                    lane_rev_str = s.lane_reversal_str.decode()

                pci_bdf = s.pci_bdf.decode() if s.pci_bdf else None
                pci_dev = s.pci_dev.decode() if s.pci_dev else None

                results.append(PortStatus(
                    port=port_id,
                    cfg_lnk_width=s.cfg_lnk_width,
                    neg_lnk_width=s.neg_lnk_width,
                    link_up=bool(s.link_up),
                    link_rate=s.link_rate,
                    ltssm=s.ltssm,
                    ltssm_str=ltssm_str_val,
                    lane_reversal=s.lane_reversal,
                    lane_reversal_str=lane_rev_str,
                    first_act_lane=s.first_act_lane,
                    pci_bdf=pci_bdf,
                    pci_dev=pci_dev,
                    vendor_id=s.vendor_id if s.vendor_id else None,
                    device_id=s.device_id if s.device_id else None,
                ))
            return results
        finally:
            self._lib.switchtec_status_free(status_ptr, nr_ports)

    def pff_to_port(self, pff: int) -> tuple[int, int]:
        """Convert PFF index to partition and port numbers.

        Returns:
            Tuple of (partition, port).
        """
        partition = c_int()
        port = c_int()
        ret = self._lib.switchtec_pff_to_port(
            self.handle, pff, ctypes.byref(partition), ctypes.byref(port)
        )
        check_error(ret, "pff_to_port")
        return partition.value, port.value

    def port_to_pff(self, partition: int, port: int) -> int:
        """Convert partition and port to PFF index."""
        pff = c_int()
        ret = self._lib.switchtec_port_to_pff(
            self.handle, partition, port, ctypes.byref(pff)
        )
        check_error(ret, "port_to_pff")
        return pff.value

    def hard_reset(self) -> None:
        """Perform a hard reset of the Switchtec device.

        This will reset the switch chip and all connected PCIe devices.
        The device handle becomes invalid after this call.
        """
        ret = self._lib.switchtec_hard_reset(self.handle)
        check_error(ret, "hard_reset")
        logger.info("device_hard_reset")

    def get_summary(self) -> DeviceSummary:
        """Get a summary of the device's current state."""
        ports = self.get_status()
        return DeviceSummary(
            name=self.name,
            device_id=self.device_id,
            generation=self.generation_str,
            variant=self.variant_str,
            boot_phase=self.boot_phase_str,
            partition=self.partition,
            fw_version=self.get_fw_version(),
            die_temperature=self.die_temperature,
            port_count=len(ports),
        )

    @staticmethod
    def list_devices() -> list[DeviceInfo]:
        """List all available Switchtec devices.

        Returns:
            List of DeviceInfo for each discovered device.
        """
        lib = _ensure_library()
        devlist_ptr = POINTER(SwitchtecDeviceInfo)()
        count = lib.switchtec_list(ctypes.byref(devlist_ptr))

        if count < 0:
            check_error(count, "list_devices")

        try:
            results: list[DeviceInfo] = []
            for i in range(count):
                d = devlist_ptr[i]
                results.append(DeviceInfo(
                    name=d.name.decode(),
                    description=d.desc.decode(),
                    pci_dev=d.pci_dev.decode(),
                    product_id=d.product_id.decode(),
                    product_rev=d.product_rev.decode(),
                    fw_version=d.fw_version.decode(),
                    path=d.path.decode(),
                ))
            return results
        finally:
            if devlist_ptr:
                lib.switchtec_list_free(devlist_ptr)
