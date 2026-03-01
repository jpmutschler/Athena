"""Switchtec device management: open, close, status, properties."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Generator
from contextlib import contextmanager
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
    InvalidParameterError,
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
    from serialcables_switchtec.core.error_injection import ErrorInjector
    from serialcables_switchtec.core.evcntr import EventCounterManager
    from serialcables_switchtec.core.events import EventManager
    from serialcables_switchtec.core.fabric import FabricManager
    from serialcables_switchtec.core.firmware import FirmwareManager
    from serialcables_switchtec.core.monitor import LinkHealthMonitor
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


MRPC_MAX_DATA_LEN = 1024

_cached_lib: ctypes.CDLL | None = None
_lib_init_lock = threading.Lock()


def _ensure_library() -> ctypes.CDLL:
    """Load and configure the library if not already done."""
    global _cached_lib
    if _cached_lib is not None:
        return _cached_lib
    with _lib_init_lock:
        if _cached_lib is not None:
            return _cached_lib
        lib = load_library()
        setup_prototypes(lib)
        _cached_lib = lib
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
        self._mgr_lock = threading.Lock()
        self._op_lock = threading.Lock()
        self._diagnostics_mgr: DiagnosticsManager | None = None
        self._evcntr_mgr: EventCounterManager | None = None
        self._events_mgr: EventManager | None = None
        self._fabric_mgr: FabricManager | None = None
        self._firmware_mgr: FirmwareManager | None = None
        self._monitor_mgr: LinkHealthMonitor | None = None
        self._osa_mgr: OrderedSetAnalyzer | None = None
        self._injector_mgr: ErrorInjector | None = None
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

    @contextmanager
    def device_op(self) -> Generator[None, None, None]:
        """Acquire the device operation lock for thread-safe C library calls.

        All core managers should use this when calling into the C library
        to prevent concurrent access to the same device handle.
        """
        with self._op_lock:
            yield

    @property
    def diagnostics(self) -> DiagnosticsManager:
        """Access diagnostics operations."""
        if self._diagnostics_mgr is None:
            with self._mgr_lock:
                if self._diagnostics_mgr is None:
                    from serialcables_switchtec.core.diagnostics import DiagnosticsManager

                    self._diagnostics_mgr = DiagnosticsManager(self)
        return self._diagnostics_mgr

    @property
    def evcntr(self) -> EventCounterManager:
        """Access event counter operations."""
        if self._evcntr_mgr is None:
            with self._mgr_lock:
                if self._evcntr_mgr is None:
                    from serialcables_switchtec.core.evcntr import EventCounterManager

                    self._evcntr_mgr = EventCounterManager(self)
        return self._evcntr_mgr

    @property
    def events(self) -> EventManager:
        """Access event management operations."""
        if self._events_mgr is None:
            with self._mgr_lock:
                if self._events_mgr is None:
                    from serialcables_switchtec.core.events import EventManager

                    self._events_mgr = EventManager(self)
        return self._events_mgr

    @property
    def firmware(self) -> FirmwareManager:
        """Access firmware management operations."""
        if self._firmware_mgr is None:
            with self._mgr_lock:
                if self._firmware_mgr is None:
                    from serialcables_switchtec.core.firmware import FirmwareManager

                    self._firmware_mgr = FirmwareManager(self)
        return self._firmware_mgr

    @property
    def monitor(self) -> LinkHealthMonitor:
        """Access link health monitoring operations."""
        if self._monitor_mgr is None:
            with self._mgr_lock:
                if self._monitor_mgr is None:
                    from serialcables_switchtec.core.monitor import LinkHealthMonitor

                    self._monitor_mgr = LinkHealthMonitor(self)
        return self._monitor_mgr

    @property
    def fabric(self) -> FabricManager:
        """Access fabric/topology operations (PAX devices only)."""
        if self._fabric_mgr is None:
            with self._mgr_lock:
                if self._fabric_mgr is None:
                    from serialcables_switchtec.core.fabric import FabricManager

                    self._fabric_mgr = FabricManager(self)
        return self._fabric_mgr

    @property
    def osa(self) -> OrderedSetAnalyzer:
        """Access Ordered Set Analyzer operations."""
        if self._osa_mgr is None:
            with self._mgr_lock:
                if self._osa_mgr is None:
                    from serialcables_switchtec.core.osa import OrderedSetAnalyzer

                    self._osa_mgr = OrderedSetAnalyzer(self)
        return self._osa_mgr

    @property
    def injector(self) -> ErrorInjector:
        """Access error injection operations."""
        if self._injector_mgr is None:
            with self._mgr_lock:
                if self._injector_mgr is None:
                    from serialcables_switchtec.core.error_injection import ErrorInjector

                    self._injector_mgr = ErrorInjector(self)
        return self._injector_mgr

    @property
    def performance(self) -> PerformanceManager:
        """Access performance monitoring operations."""
        if self._performance_mgr is None:
            with self._mgr_lock:
                if self._performance_mgr is None:
                    from serialcables_switchtec.core.performance import PerformanceManager

                    self._performance_mgr = PerformanceManager(self)
        return self._performance_mgr

    @property
    def name(self) -> str:
        """Device name."""
        with self.device_op():
            result = self._lib.switchtec_name(self.handle)
        return result.decode() if result else ""

    @property
    def partition(self) -> int:
        """Current partition number."""
        with self.device_op():
            return self._lib.switchtec_partition(self.handle)

    @property
    def device_id(self) -> int:
        """PCI device ID."""
        with self.device_op():
            return self._lib.switchtec_device_id(self.handle)

    @property
    def generation(self) -> SwitchtecGen:
        """PCIe generation."""
        with self.device_op():
            return SwitchtecGen(self._lib.switchtec_gen(self.handle))

    @property
    def generation_str(self) -> str:
        """PCIe generation as a string."""
        return _GEN_NAMES.get(self.generation, "Unknown")

    @property
    def variant(self) -> SwitchtecVariant:
        """Device variant (PFX, PSX, PAX, etc.)."""
        with self.device_op():
            return SwitchtecVariant(self._lib.switchtec_variant(self.handle))

    @property
    def variant_str(self) -> str:
        """Device variant as a string."""
        return _VARIANT_NAMES.get(self.variant, "Unknown")

    @property
    def boot_phase(self) -> SwitchtecBootPhase:
        """Current boot phase."""
        with self.device_op():
            return SwitchtecBootPhase(self._lib.switchtec_boot_phase(self.handle))

    @property
    def boot_phase_str(self) -> str:
        """Boot phase as a string."""
        return _PHASE_NAMES.get(self.boot_phase, "Unknown Phase")

    @property
    def die_temperature(self) -> float:
        """Die temperature in degrees Celsius."""
        with self.device_op():
            return self._lib.switchtec_die_temp(self.handle)

    def get_die_temperatures(self, nr_sensors: int = 5) -> list[float]:
        """Get temperature readings from multiple sensors.

        Args:
            nr_sensors: Number of sensors to read.

        Returns:
            List of temperature readings in degrees Celsius.
        """
        readings = (c_float * nr_sensors)()
        with self.device_op():
            ret = self._lib.switchtec_die_temps(self.handle, nr_sensors, readings)
        check_error(ret, "die_temps")
        return [readings[i] for i in range(nr_sensors)]

    def get_fw_version(self) -> str:
        """Get firmware version string."""
        buf = ctypes.create_string_buffer(256)
        with self.device_op():
            ret = self._lib.switchtec_get_fw_version(self.handle, buf, 256)
        check_error(ret, "get_fw_version")
        return buf.value.decode()

    def get_status(self) -> list[PortStatus]:
        """Get status of all ports.

        Returns:
            List of PortStatus for each port.
        """
        status_ptr = POINTER(SwitchtecStatus)()
        nr_ports = 0
        with self.device_op():
            nr_ports = self._lib.switchtec_status(
                self.handle, ctypes.byref(status_ptr)
            )
            check_error(nr_ports, "status")

        # Wrap all post-status work in try/finally so status_free is
        # always called, even if get_devices or result processing fails.
        try:
            with self.device_op():
                # Populate device info within same lock scope.
                # get_devices is a separate C call but operates on the
                # status_ptr allocated above, not a new device query.
                self._lib.switchtec_get_devices(
                    self.handle, status_ptr, nr_ports
                )

            # Process results outside the lock
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
        with self.device_op():
            ret = self._lib.switchtec_pff_to_port(
                self.handle, pff, ctypes.byref(partition), ctypes.byref(port)
            )
        check_error(ret, "pff_to_port")
        return partition.value, port.value

    def port_to_pff(self, partition: int, port: int) -> int:
        """Convert partition and port to PFF index."""
        pff = c_int()
        with self.device_op():
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
        with self.device_op():
            ret = self._lib.switchtec_hard_reset(self.handle)
        check_error(ret, "hard_reset")
        self._closed = True
        logger.info("device_hard_reset")

    def mrpc_cmd(
        self,
        cmd: int,
        payload: bytes = b"",
        resp_len: int = 0,
    ) -> bytes:
        """Send a raw MRPC command to the device.

        This is a low-level interface for sending arbitrary MRPC commands.
        Most users should prefer the typed manager APIs. Use this for
        debugging, firmware development, or accessing commands not yet
        wrapped by the Python API.

        Args:
            cmd: MRPC command ID (uint32).
            payload: Command payload bytes. Empty for commands with no
                payload.
            resp_len: Expected response length in bytes. 0 if no response.

        Returns:
            Response bytes (empty if resp_len is 0).

        Raises:
            SwitchtecError: If the MRPC command fails.
        """
        if len(payload) > MRPC_MAX_DATA_LEN:
            raise InvalidParameterError(
                f"MRPC payload size {len(payload)} exceeds maximum "
                f"{MRPC_MAX_DATA_LEN} bytes"
            )
        if resp_len > MRPC_MAX_DATA_LEN:
            raise InvalidParameterError(
                f"MRPC response length {resp_len} exceeds maximum "
                f"{MRPC_MAX_DATA_LEN} bytes"
            )

        logger.warning(
            "mrpc_raw_command",
            cmd=f"0x{cmd:x}",
            payload_len=len(payload) if payload else 0,
            resp_len=resp_len,
        )

        payload_buf = (
            ctypes.create_string_buffer(payload) if payload else None
        )
        payload_len = len(payload) if payload else 0

        if resp_len > 0:
            resp_buf = ctypes.create_string_buffer(resp_len)
        else:
            resp_buf = None

        with self.device_op():
            ret = self._lib.switchtec_cmd(
                self.handle,
                cmd,
                payload_buf,
                payload_len,
                resp_buf,
                resp_len,
            )
        check_error(ret, f"mrpc_cmd(0x{cmd:x})")

        if resp_buf is not None:
            return resp_buf.raw[:resp_len]
        return b""

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
