"""ctypes Structure definitions matching Switchtec C headers.

Field names preserve the original C naming convention for direct mapping.
"""

from __future__ import annotations

import ctypes
from ctypes import Structure, c_char, c_int, c_uint8, c_uint16, c_uint32, c_uint64, c_float

from serialcables_switchtec.bindings.constants import (
    MAX_PARTS,
    MAX_PORTS,
    MAX_PFF_CSR,
    PATH_MAX,
    DIAG_MAX_TLP_DWORDS,
)


# ─── Device Info (from switchtec_list) ───────────────────────────────

class SwitchtecDeviceInfo(Structure):
    """Matches struct switchtec_device_info in switchtec.h."""

    _fields_ = [
        ("name", c_char * 256),
        ("desc", c_char * 256),
        ("pci_dev", c_char * 256),
        ("product_id", c_char * 32),
        ("product_rev", c_char * 8),
        ("fw_version", c_char * 32),
        ("path", c_char * PATH_MAX),
    ]


# ─── Port ID ────────────────────────────────────────────────────────

class SwitchtecPortId(Structure):
    """Matches struct switchtec_port_id in switchtec.h."""

    _fields_ = [
        ("partition", c_uint8),
        ("stack", c_uint8),
        ("upstream", c_uint8),
        ("stk_id", c_uint8),
        ("phys_id", c_uint8),
        ("log_id", c_uint8),
    ]


# ─── Port Status ────────────────────────────────────────────────────

class SwitchtecStatus(Structure):
    """Matches struct switchtec_status in switchtec.h."""

    _fields_ = [
        ("port", SwitchtecPortId),
        ("cfg_lnk_width", c_uint8),
        ("neg_lnk_width", c_uint8),
        ("link_up", c_uint8),
        ("link_rate", c_uint8),
        ("ltssm", c_uint16),
        ("ltssm_str", ctypes.c_char_p),
        ("lane_reversal", c_uint8),
        ("lane_reversal_str", ctypes.c_char_p),
        ("first_act_lane", c_uint8),
        ("lanes", c_char * 17),
        ("pci_bdf", ctypes.c_char_p),
        ("pci_bdf_path", ctypes.c_char_p),
        ("pci_dev", ctypes.c_char_p),
        ("vendor_id", c_int),
        ("device_id", c_int),
        ("class_devices", ctypes.c_char_p),
        ("acs_ctrl", ctypes.c_uint),
    ]


# ─── Event Summary ──────────────────────────────────────────────────

class SwitchtecEventSummary(Structure):
    """Matches struct switchtec_event_summary in switchtec.h."""

    _fields_ = [
        ("global_events", c_uint64),
        ("part_bitmap", c_uint64),
        ("local_part", ctypes.c_uint),
        ("part", ctypes.c_uint * MAX_PARTS),
        ("pff", ctypes.c_uint * MAX_PFF_CSR),
    ]


# ─── Firmware Image Info ────────────────────────────────────────────

class SwitchtecFwImageInfo(Structure):
    """Matches struct switchtec_fw_image_info in switchtec.h."""

    _fields_ = [
        ("gen", c_int),
        ("part_id", c_uint32),
        ("type", c_int),
        ("version", c_char * 32),
        ("part_addr", ctypes.c_size_t),
        ("part_len", ctypes.c_size_t),
        ("part_body_offset", ctypes.c_size_t),
        ("image_len", ctypes.c_size_t),
        ("image_crc", c_uint32),
        ("valid", ctypes.c_bool),
        ("active", ctypes.c_bool),
        ("running", ctypes.c_bool),
        ("read_only", ctypes.c_bool),
        ("next", ctypes.c_void_p),  # Pointer to next info
        ("metadata", ctypes.c_void_p),
        ("secure_version", c_uint32),
        ("signed_image", ctypes.c_bool),
        ("redundant", c_uint8),
    ]


# ─── Bandwidth Counter ──────────────────────────────────────────────

class SwitchtecBwCntrDir(Structure):
    """Matches struct switchtec_bwcntr_dir in switchtec.h."""

    _fields_ = [
        ("posted", c_uint64),
        ("comp", c_uint64),
        ("nonposted", c_uint64),
    ]


class SwitchtecBwCntrRes(Structure):
    """Matches struct switchtec_bwcntr_res in switchtec.h."""

    _fields_ = [
        ("time_us", c_uint64),
        ("egress", SwitchtecBwCntrDir),
        ("ingress", SwitchtecBwCntrDir),
    ]


# ─── Range (from utils.h, used for eye diagrams) ────────────────────

class Range(Structure):
    """Matches struct range in utils.h."""

    _fields_ = [
        ("start", c_int),
        ("end", c_int),
        ("step", c_int),
    ]


# ─── Diagnostic Structures ──────────────────────────────────────────

class SwitchtecDiagCrossHair(Structure):
    """Matches struct switchtec_diag_cross_hair in switchtec.h."""

    _fields_ = [
        ("state", c_int),
        ("lane_id", c_int),
        # Union: error fields or done fields
        ("eye_left_lim", c_int),  # Also prev_state when state==ERROR
        ("eye_right_lim", c_int),  # Also x_pos when state==ERROR
        ("eye_bot_left_lim", c_int),  # Also y_pos when state==ERROR
        ("eye_bot_right_lim", c_int),
        ("eye_top_left_lim", c_int),
        ("eye_top_right_lim", c_int),
    ]


class SwitchtecRcvrObj(Structure):
    """Matches struct switchtec_rcvr_obj in switchtec.h."""

    _fields_ = [
        ("port_id", c_int),
        ("lane_id", c_int),
        ("ctle", c_int),
        ("target_amplitude", c_int),
        ("speculative_dfe", c_int),
        ("dynamic_dfe", c_int * 7),
    ]


class SwitchtecRcvrExt(Structure):
    """Matches struct switchtec_rcvr_ext in switchtec.h."""

    _fields_ = [
        ("ctle2_rx_mode", c_int),
        ("dtclk_5", c_int),
        ("dtclk_8_6", c_int),
        ("dtclk_9", c_int),
    ]


class SwitchtecPortEqCursor(Structure):
    """Cursor pair for equalization coefficients."""

    _fields_ = [
        ("pre", c_uint8),
        ("post", c_uint8),
    ]


class SwitchtecPortEqCoeff(Structure):
    """Matches struct switchtec_port_eq_coeff in switchtec.h."""

    _fields_ = [
        ("lane_cnt", c_uint8),
        ("reserved", c_uint8 * 3),
        ("cursors", SwitchtecPortEqCursor * 16),
    ]


class SwitchtecPortEqTableStep(Structure):
    """Single step in equalization table."""

    _fields_ = [
        ("pre_cursor", c_int),
        ("post_cursor", c_int),
        ("fom", c_int),
        ("pre_cursor_up", c_int),
        ("post_cursor_up", c_int),
        ("error_status", c_int),
        ("active_status", c_int),
        ("speed", c_int),
    ]


class SwitchtecPortEqTable(Structure):
    """Matches struct switchtec_port_eq_table in switchtec.h."""

    _fields_ = [
        ("lane_id", c_int),
        ("step_cnt", c_int),
        ("steps", SwitchtecPortEqTableStep * 126),
    ]


class SwitchtecPortEqTxFslf(Structure):
    """Matches struct switchtec_port_eq_tx_fslf in switchtec.h."""

    _fields_ = [
        ("fs", c_int),
        ("lf", c_int),
    ]


class SwitchtecDiagLtssmLog(Structure):
    """Matches struct switchtec_diag_ltssm_log in switchtec.h."""

    _fields_ = [
        ("timestamp", c_uint32),
        ("link_rate", c_float),
        ("link_state", c_int),
        ("link_width", c_int),
        ("tx_minor_state", c_int),
        ("rx_minor_state", c_int),
    ]


# ─── Fabric Structures ────────────────────────────────────────────

class SwitchtecFabPortConfig(Structure):
    """Fabric port configuration structure."""

    _pack_ = 1
    _fields_ = [
        ("port_type", c_uint8),
        ("clock_source", c_uint8),
        ("clock_sris", c_uint8),
        ("hvd_inst", c_uint8),
        ("link_width", c_uint8),
    ]


class SwitchtecGfmsBindReq(Structure):
    """GFMS bind request structure."""

    _pack_ = 1
    _fields_ = [
        ("host_sw_idx", c_uint8),
        ("host_phys_port_id", c_uint8),
        ("host_log_port_id", c_uint8),
        ("ep_sw_idx", c_uint8),
        ("ep_phys_port_id", c_uint8),
    ]


class SwitchtecGfmsUnbindReq(Structure):
    """GFMS unbind request structure."""

    _pack_ = 1
    _fields_ = [
        ("host_sw_idx", c_uint8),
        ("host_phys_port_id", c_uint8),
        ("host_log_port_id", c_uint8),
        ("opt", c_uint8),
    ]
