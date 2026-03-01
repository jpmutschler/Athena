"""Diagnostics manager for eye diagrams, LTSSM, loopback, pattern, EQ, cross-hair."""

from __future__ import annotations

import ctypes
from ctypes import POINTER, c_double, c_int, c_uint64

from serialcables_switchtec.bindings.constants import (
    DiagCrossHairState,
    DiagEnd,
    DiagLink,
    DiagLtssmSpeed,
    DiagPattern,
    DiagPatternLinkRate,
    SwitchtecGen,
    ltssm_str,
)
from serialcables_switchtec.bindings.types import (
    Range,
    SwitchtecDiagCrossHair,
    SwitchtecDiagLtssmLog,
    SwitchtecPortEqCoeff,
    SwitchtecPortEqTable,
    SwitchtecPortEqTxFslf,
    SwitchtecRcvrExt,
    SwitchtecRcvrObj,
)
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.models.diagnostics import (
    CrossHairResult,
    EqCursor,
    EqTableStep,
    EyeData,
    EyeRange,
    LoopbackStatus,
    LtssmLogEntry,
    PatternMonResult,
    PortEqCoeff,
    PortEqTable,
    PortEqTxFslf,
    ReceiverExt,
    ReceiverObject,
)
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)


class DiagnosticsManager:
    """Diagnostics operations on a Switchtec device.

    Requires a SwitchtecDevice instance to operate on.
    """

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device
        self._eye_x_range: EyeRange | None = None
        self._eye_y_range: EyeRange | None = None

    # ─── Eye Diagram ─────────────────────────────────────────────────

    def eye_start(
        self,
        lane_mask: list[int],
        x_start: int = -64,
        x_end: int = 64,
        x_step: int = 1,
        y_start: int = -255,
        y_end: int = 255,
        y_step: int = 2,
        step_interval: int = 10,
        capture_depth: int = 0,
        sar_sel: int = 0,
        intleav_sel: int = 0,
        hstep: int = 0,
        data_mode: int = 0,
        eye_mode: int = 0,
        refclk: int = 0,
        vstep: int = 0,
    ) -> None:
        """Start an eye diagram capture."""
        mask = (c_int * 4)(*lane_mask[:4])
        x_range = Range(start=x_start, end=x_end, step=x_step)
        y_range = Range(start=y_start, end=y_end, step=y_step)

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_eye_start(
                self._dev.handle, mask,
                ctypes.byref(x_range), ctypes.byref(y_range),
                step_interval, capture_depth, sar_sel, intleav_sel,
                hstep, data_mode, eye_mode, refclk, vstep,
            )
            check_error(ret, "eye_start")
            self._eye_x_range = EyeRange(start=x_start, end=x_end, step=x_step)
            self._eye_y_range = EyeRange(start=y_start, end=y_end, step=y_step)
        logger.info("eye_capture_started", lane_mask=lane_mask)

    def eye_fetch(self, pixel_count: int) -> EyeData:
        """Fetch eye diagram data.

        Args:
            pixel_count: Expected number of pixels to fetch.

        Returns:
            EyeData with captured pixels.
        """
        pixels = (c_double * pixel_count)()
        lane_id = c_int()

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_eye_fetch(
                self._dev.handle, pixels, pixel_count, ctypes.byref(lane_id)
            )
        check_error(ret, "eye_fetch")

        x_range = self._eye_x_range or EyeRange(start=0, end=0, step=1)
        y_range = self._eye_y_range or EyeRange(start=0, end=0, step=1)

        return EyeData(
            lane_id=lane_id.value,
            x_range=x_range,
            y_range=y_range,
            pixels=[pixels[i] for i in range(pixel_count)],
        )

    def eye_cancel(self) -> None:
        """Cancel an in-progress eye diagram capture."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_eye_cancel(self._dev.handle)
            self._eye_x_range = None
            self._eye_y_range = None
        check_error(ret, "eye_cancel")

    def eye_set_mode(self, mode: int) -> None:
        """Set eye diagram data mode (raw vs ratio)."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_eye_set_mode(self._dev.handle, mode)
        check_error(ret, "eye_set_mode")

    def eye_read(
        self, lane_id: int, bin_idx: int, max_phases: int = 60
    ) -> tuple[int, list[float]]:
        """Read eye diagram BER data for Gen5+.

        Returns:
            Tuple of (num_phases, ber_data).
        """
        num_phases = c_int()
        ber_data = (c_double * max_phases)()

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_eye_read(
                self._dev.handle, lane_id, bin_idx,
                ctypes.byref(num_phases), ber_data,
            )
        check_error(ret, "eye_read")
        return num_phases.value, [ber_data[i] for i in range(num_phases.value)]

    # ─── LTSSM Log ──────────────────────────────────────────────────

    def ltssm_log(
        self, port_id: int, max_entries: int = 64
    ) -> list[LtssmLogEntry]:
        """Dump LTSSM state log for a port.

        Args:
            port_id: Physical port ID.
            max_entries: Maximum log entries to read.

        Returns:
            List of LTSSM log entries.
        """
        log_count = c_int(max_entries)
        log_data = (SwitchtecDiagLtssmLog * max_entries)()

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_ltssm_log(
                self._dev.handle, port_id, ctypes.byref(log_count), log_data
            )
        check_error(ret, "ltssm_log")

        gen = self._dev.generation
        results: list[LtssmLogEntry] = []
        for i in range(log_count.value):
            entry = log_data[i]
            state_str = ltssm_str(entry.link_state, gen)
            results.append(LtssmLogEntry(
                timestamp=entry.timestamp,
                link_rate=entry.link_rate,
                link_state=entry.link_state,
                link_state_str=state_str,
                link_width=entry.link_width,
                tx_minor_state=entry.tx_minor_state,
                rx_minor_state=entry.rx_minor_state,
            ))
        return results

    def ltssm_clear(self, port_id: int) -> None:
        """Clear LTSSM log for a port."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_ltssm_clear(self._dev.handle, port_id)
        check_error(ret, "ltssm_clear")

    # ─── Loopback ───────────────────────────────────────────────────

    def loopback_set(
        self,
        port_id: int,
        enable: bool = True,
        enable_parallel: bool = False,
        enable_external: bool = False,
        enable_ltssm: bool = False,
        enable_pipe: bool = False,
        ltssm_speed: DiagLtssmSpeed = DiagLtssmSpeed.GEN4,
    ) -> None:
        """Configure loopback on a port."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_loopback_set(
                self._dev.handle, port_id,
                int(enable), int(enable_parallel), int(enable_external),
                int(enable_ltssm), int(enable_pipe), int(ltssm_speed),
            )
        check_error(ret, "loopback_set")

    def loopback_get(self, port_id: int) -> LoopbackStatus:
        """Get loopback status for a port."""
        enabled = c_int()
        ltssm_speed = c_int()

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_loopback_get(
                self._dev.handle, port_id,
                ctypes.byref(enabled), ctypes.byref(ltssm_speed),
            )
        check_error(ret, "loopback_get")

        return LoopbackStatus(
            port_id=port_id,
            enabled=enabled.value,
            ltssm_speed=ltssm_speed.value,
        )

    # ─── Pattern Generator / Monitor ────────────────────────────────

    def pattern_gen_set(
        self,
        port_id: int,
        pattern: DiagPattern = DiagPattern.PRBS_31,
        link_speed: DiagPatternLinkRate = DiagPatternLinkRate.GEN4,
    ) -> None:
        """Set pattern generator on a port."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_pattern_gen_set(
                self._dev.handle, port_id, int(pattern), int(link_speed)
            )
        check_error(ret, "pattern_gen_set")

    def pattern_gen_get(self, port_id: int) -> int:
        """Get current pattern generator type for a port."""
        pattern_type = c_int()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_pattern_gen_get(
                self._dev.handle, port_id, ctypes.byref(pattern_type)
            )
        check_error(ret, "pattern_gen_get")
        return pattern_type.value

    def pattern_mon_set(
        self, port_id: int, pattern: DiagPattern = DiagPattern.PRBS_31
    ) -> None:
        """Set pattern monitor on a port."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_pattern_mon_set(
                self._dev.handle, port_id, int(pattern)
            )
        check_error(ret, "pattern_mon_set")

    def pattern_mon_get(
        self, port_id: int, lane_id: int
    ) -> PatternMonResult:
        """Get pattern monitor results for a port/lane."""
        pattern_type = c_int()
        err_cnt = c_uint64()

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_pattern_mon_get(
                self._dev.handle, port_id, lane_id,
                ctypes.byref(pattern_type), ctypes.byref(err_cnt),
            )
        check_error(ret, "pattern_mon_get")

        return PatternMonResult(
            port_id=port_id,
            lane_id=lane_id,
            pattern_type=pattern_type.value,
            error_count=err_cnt.value,
        )

    def pattern_inject(self, port_id: int, err_count: int = 1) -> None:
        """Inject errors into pattern stream."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_pattern_inject(
                self._dev.handle, port_id, err_count
            )
        check_error(ret, "pattern_inject")

    # ─── Receiver Object ────────────────────────────────────────────

    def rcvr_obj(
        self,
        port_id: int,
        lane_id: int,
        link: DiagLink = DiagLink.CURRENT,
    ) -> ReceiverObject:
        """Dump receiver calibration object."""
        result = SwitchtecRcvrObj()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_rcvr_obj(
                self._dev.handle, port_id, lane_id, int(link), ctypes.byref(result)
            )
        check_error(ret, "rcvr_obj")

        return ReceiverObject(
            port_id=result.port_id,
            lane_id=result.lane_id,
            ctle=result.ctle,
            target_amplitude=result.target_amplitude,
            speculative_dfe=result.speculative_dfe,
            dynamic_dfe=[result.dynamic_dfe[i] for i in range(7)],
        )

    def rcvr_ext(
        self,
        port_id: int,
        lane_id: int,
        link: DiagLink = DiagLink.CURRENT,
    ) -> ReceiverExt:
        """Dump extended receiver calibration data."""
        result = SwitchtecRcvrExt()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_rcvr_ext(
                self._dev.handle, port_id, lane_id, int(link), ctypes.byref(result)
            )
        check_error(ret, "rcvr_ext")

        return ReceiverExt(
            ctle2_rx_mode=result.ctle2_rx_mode,
            dtclk_5=result.dtclk_5,
            dtclk_8_6=result.dtclk_8_6,
            dtclk_9=result.dtclk_9,
        )

    # ─── Port Equalization ──────────────────────────────────────────

    def port_eq_tx_coeff(
        self,
        port_id: int,
        prev_speed: int = 0,
        end: DiagEnd = DiagEnd.LOCAL,
        link: DiagLink = DiagLink.CURRENT,
    ) -> PortEqCoeff:
        """Get port equalization TX coefficients."""
        result = SwitchtecPortEqCoeff()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_port_eq_tx_coeff(
                self._dev.handle, port_id, prev_speed,
                int(end), int(link), ctypes.byref(result),
            )
        check_error(ret, "port_eq_tx_coeff")

        cursors = [
            EqCursor(pre=result.cursors[i].pre, post=result.cursors[i].post)
            for i in range(result.lane_cnt)
        ]
        return PortEqCoeff(lane_count=result.lane_cnt, cursors=cursors)

    def port_eq_tx_table(
        self,
        port_id: int,
        prev_speed: int = 0,
        link: DiagLink = DiagLink.CURRENT,
    ) -> PortEqTable:
        """Get port equalization table."""
        result = SwitchtecPortEqTable()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_port_eq_tx_table(
                self._dev.handle, port_id, prev_speed, int(link), ctypes.byref(result)
            )
        check_error(ret, "port_eq_tx_table")

        steps = [
            EqTableStep(
                pre_cursor=result.steps[i].pre_cursor,
                post_cursor=result.steps[i].post_cursor,
                fom=result.steps[i].fom,
                pre_cursor_up=result.steps[i].pre_cursor_up,
                post_cursor_up=result.steps[i].post_cursor_up,
                error_status=result.steps[i].error_status,
                active_status=result.steps[i].active_status,
                speed=result.steps[i].speed,
            )
            for i in range(result.step_cnt)
        ]
        return PortEqTable(
            lane_id=result.lane_id,
            step_count=result.step_cnt,
            steps=steps,
        )

    def port_eq_tx_fslf(
        self,
        port_id: int,
        prev_speed: int = 0,
        lane_id: int = 0,
        end: DiagEnd = DiagEnd.LOCAL,
        link: DiagLink = DiagLink.CURRENT,
    ) -> PortEqTxFslf:
        """Get port equalization TX FS/LF values."""
        result = SwitchtecPortEqTxFslf()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_port_eq_tx_fslf(
                self._dev.handle, port_id, prev_speed, lane_id,
                int(end), int(link), ctypes.byref(result),
            )
        check_error(ret, "port_eq_tx_fslf")
        return PortEqTxFslf(fs=result.fs, lf=result.lf)

    # ─── Cross Hair ─────────────────────────────────────────────────

    def cross_hair_enable(self, lane_id: int) -> None:
        """Enable cross-hair measurement on a lane."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_cross_hair_enable(
                self._dev.handle, lane_id
            )
        check_error(ret, "cross_hair_enable")

    def cross_hair_disable(self) -> None:
        """Disable cross-hair measurement."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_cross_hair_disable(self._dev.handle)
        check_error(ret, "cross_hair_disable")

    def cross_hair_get(
        self, start_lane_id: int = 0, num_lanes: int = 1
    ) -> list[CrossHairResult]:
        """Get cross-hair measurement results."""
        results_arr = (SwitchtecDiagCrossHair * num_lanes)()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_diag_cross_hair_get(
                self._dev.handle, start_lane_id, num_lanes, results_arr
            )
        check_error(ret, "cross_hair_get")

        results: list[CrossHairResult] = []
        for i in range(num_lanes):
            ch = results_arr[i]
            try:
                state_name = DiagCrossHairState(ch.state).name
            except ValueError:
                state_name = f"UNKNOWN({ch.state})"

            results.append(CrossHairResult(
                lane_id=ch.lane_id,
                state=ch.state,
                state_name=state_name,
                eye_left_lim=ch.eye_left_lim,
                eye_right_lim=ch.eye_right_lim,
                eye_bot_left_lim=ch.eye_bot_left_lim,
                eye_bot_right_lim=ch.eye_bot_right_lim,
                eye_top_left_lim=ch.eye_top_left_lim,
                eye_top_right_lim=ch.eye_top_right_lim,
            ))
        return results
