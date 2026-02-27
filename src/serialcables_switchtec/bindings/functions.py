"""Function prototypes (argtypes/restype) for the Switchtec C library.

Configures ctypes function signatures for type safety and proper
marshalling. Call setup_prototypes() after loading the library.
"""

from __future__ import annotations

import ctypes
from ctypes import (
    POINTER,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_size_t,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    c_void_p,
)

from serialcables_switchtec.bindings.types import (
    Range,
    SwitchtecBwCntrRes,
    SwitchtecDeviceInfo,
    SwitchtecDiagCrossHair,
    SwitchtecDiagLtssmLog,
    SwitchtecEventSummary,
    SwitchtecFabPortConfig,
    SwitchtecFwImageInfo,
    SwitchtecGfmsBindReq,
    SwitchtecGfmsUnbindReq,
    SwitchtecPortEqCoeff,
    SwitchtecPortEqTable,
    SwitchtecPortEqTxFslf,
    SwitchtecPortId,
    SwitchtecRcvrExt,
    SwitchtecRcvrObj,
    SwitchtecStatus,
)


def setup_prototypes(lib: ctypes.CDLL) -> None:
    """Configure all function prototypes on the loaded library.

    Args:
        lib: The loaded Switchtec CDLL instance.
    """
    _setup_platform_functions(lib)
    _setup_accessor_functions(lib)
    _setup_status_functions(lib)
    _setup_event_functions(lib)
    _setup_fw_functions(lib)
    _setup_bw_lat_functions(lib)
    _setup_diag_functions(lib)
    _setup_inject_functions(lib)
    _setup_osa_functions(lib)
    _setup_fabric_functions(lib)


def _setup_platform_functions(lib: ctypes.CDLL) -> None:
    """Platform functions: open, close, list."""

    # struct switchtec_dev *switchtec_open(const char *device)
    lib.switchtec_open.argtypes = [c_char_p]
    lib.switchtec_open.restype = c_void_p
    lib.switchtec_open.errcheck = None

    # struct switchtec_dev *switchtec_open_by_index(int index)
    lib.switchtec_open_by_index.argtypes = [c_int]
    lib.switchtec_open_by_index.restype = c_void_p

    # struct switchtec_dev *switchtec_open_by_pci_addr(int domain, int bus,
    #     int device, int func)
    lib.switchtec_open_by_pci_addr.argtypes = [c_int, c_int, c_int, c_int]
    lib.switchtec_open_by_pci_addr.restype = c_void_p

    # void switchtec_close(struct switchtec_dev *dev)
    lib.switchtec_close.argtypes = [c_void_p]
    lib.switchtec_close.restype = None

    # int switchtec_list(struct switchtec_device_info **devlist)
    lib.switchtec_list.argtypes = [POINTER(POINTER(SwitchtecDeviceInfo))]
    lib.switchtec_list.restype = c_int

    # void switchtec_list_free(struct switchtec_device_info *devlist)
    lib.switchtec_list_free.argtypes = [POINTER(SwitchtecDeviceInfo)]
    lib.switchtec_list_free.restype = None

    # int switchtec_get_fw_version(struct switchtec_dev *dev, char *buf,
    #     size_t buflen)
    lib.switchtec_get_fw_version.argtypes = [c_void_p, c_char_p, c_size_t]
    lib.switchtec_get_fw_version.restype = c_int

    # int switchtec_cmd(struct switchtec_dev *dev, uint32_t cmd,
    #     const void *payload, size_t payload_len, void *resp, size_t resp_len)
    lib.switchtec_cmd.argtypes = [c_void_p, c_uint32, c_void_p, c_size_t, c_void_p, c_size_t]
    lib.switchtec_cmd.restype = c_int

    # int switchtec_get_devices(struct switchtec_dev *dev,
    #     struct switchtec_status *status, int ports)
    lib.switchtec_get_devices.argtypes = [c_void_p, POINTER(SwitchtecStatus), c_int]
    lib.switchtec_get_devices.restype = c_int

    # int switchtec_pff_to_port(struct switchtec_dev *dev, int pff,
    #     int *partition, int *port)
    lib.switchtec_pff_to_port.argtypes = [c_void_p, c_int, POINTER(c_int), POINTER(c_int)]
    lib.switchtec_pff_to_port.restype = c_int

    # int switchtec_port_to_pff(struct switchtec_dev *dev, int partition,
    #     int port, int *pff)
    lib.switchtec_port_to_pff.argtypes = [c_void_p, c_int, c_int, POINTER(c_int)]
    lib.switchtec_port_to_pff.restype = c_int

    # const char *switchtec_strerror(void)
    lib.switchtec_strerror.argtypes = []
    lib.switchtec_strerror.restype = c_char_p

    # void switchtec_perror(const char *str)
    lib.switchtec_perror.argtypes = [c_char_p]
    lib.switchtec_perror.restype = None


def _setup_accessor_functions(lib: ctypes.CDLL) -> None:
    """Generic accessor functions: name, partition, device_id, etc."""

    # const char *switchtec_name(struct switchtec_dev *dev)
    lib.switchtec_name.argtypes = [c_void_p]
    lib.switchtec_name.restype = c_char_p

    # int switchtec_partition(struct switchtec_dev *dev)
    lib.switchtec_partition.argtypes = [c_void_p]
    lib.switchtec_partition.restype = c_int

    # int switchtec_device_id(struct switchtec_dev *dev)
    lib.switchtec_device_id.argtypes = [c_void_p]
    lib.switchtec_device_id.restype = c_int

    # enum switchtec_gen switchtec_gen(struct switchtec_dev *dev)
    lib.switchtec_gen.argtypes = [c_void_p]
    lib.switchtec_gen.restype = c_int

    # enum switchtec_variant switchtec_variant(struct switchtec_dev *dev)
    lib.switchtec_variant.argtypes = [c_void_p]
    lib.switchtec_variant.restype = c_int

    # enum switchtec_boot_phase switchtec_boot_phase(struct switchtec_dev *dev)
    lib.switchtec_boot_phase.argtypes = [c_void_p]
    lib.switchtec_boot_phase.restype = c_int


def _setup_status_functions(lib: ctypes.CDLL) -> None:
    """Status and temperature functions."""

    # int switchtec_status(struct switchtec_dev *dev,
    #     struct switchtec_status **status)
    lib.switchtec_status.argtypes = [c_void_p, POINTER(POINTER(SwitchtecStatus))]
    lib.switchtec_status.restype = c_int

    # void switchtec_status_free(struct switchtec_status *status, int ports)
    lib.switchtec_status_free.argtypes = [POINTER(SwitchtecStatus), c_int]
    lib.switchtec_status_free.restype = None

    # float switchtec_die_temp(struct switchtec_dev *dev)
    lib.switchtec_die_temp.argtypes = [c_void_p]
    lib.switchtec_die_temp.restype = c_float

    # int switchtec_die_temps(struct switchtec_dev *dev, int nr_sensor,
    #     float *sensor_readings)
    lib.switchtec_die_temps.argtypes = [c_void_p, c_int, POINTER(c_float)]
    lib.switchtec_die_temps.restype = c_int

    # int switchtec_get_device_info(struct switchtec_dev *dev,
    #     enum switchtec_boot_phase *phase, enum switchtec_gen *gen,
    #     enum switchtec_rev *rev)
    lib.switchtec_get_device_info.argtypes = [
        c_void_p,
        POINTER(c_int),
        POINTER(c_int),
        POINTER(c_int),
    ]
    lib.switchtec_get_device_info.restype = c_int

    # int switchtec_hard_reset(struct switchtec_dev *dev)
    lib.switchtec_hard_reset.argtypes = [c_void_p]
    lib.switchtec_hard_reset.restype = c_int

    # int switchtec_calc_lane_id(struct switchtec_dev *dev, int phys_port_id,
    #     int lane_id, struct switchtec_status *port)
    lib.switchtec_calc_lane_id.argtypes = [c_void_p, c_int, c_int, POINTER(SwitchtecStatus)]
    lib.switchtec_calc_lane_id.restype = c_int


def _setup_event_functions(lib: ctypes.CDLL) -> None:
    """Event handling functions."""

    # int switchtec_event_summary(struct switchtec_dev *dev,
    #     struct switchtec_event_summary *sum)
    lib.switchtec_event_summary.argtypes = [c_void_p, POINTER(SwitchtecEventSummary)]
    lib.switchtec_event_summary.restype = c_int

    # int switchtec_event_ctl(struct switchtec_dev *dev,
    #     enum switchtec_event_id e, int index, int flags, uint32_t data[5])
    lib.switchtec_event_ctl.argtypes = [c_void_p, c_int, c_int, c_int, POINTER(c_uint32)]
    lib.switchtec_event_ctl.restype = c_int

    # int switchtec_event_wait(struct switchtec_dev *dev, int timeout_ms)
    lib.switchtec_event_wait.argtypes = [c_void_p, c_int]
    lib.switchtec_event_wait.restype = c_int


def _setup_fw_functions(lib: ctypes.CDLL) -> None:
    """Firmware management functions."""

    # int switchtec_fw_toggle_active_partition(struct switchtec_dev *dev,
    #     int toggle_bl2, int toggle_key, int toggle_fw, int toggle_cfg,
    #     int toggle_riotcore)
    lib.switchtec_fw_toggle_active_partition.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
    ]
    lib.switchtec_fw_toggle_active_partition.restype = c_int

    # int switchtec_fw_read(struct switchtec_dev *dev, unsigned long addr,
    #     size_t len, void *buf)
    lib.switchtec_fw_read.argtypes = [c_void_p, ctypes.c_ulong, c_size_t, c_void_p]
    lib.switchtec_fw_read.restype = c_int

    # struct switchtec_fw_part_summary *
    # switchtec_fw_part_summary(struct switchtec_dev *dev)
    lib.switchtec_fw_part_summary.argtypes = [c_void_p]
    lib.switchtec_fw_part_summary.restype = c_void_p

    # void switchtec_fw_part_summary_free(
    #     struct switchtec_fw_part_summary *summary)
    lib.switchtec_fw_part_summary_free.argtypes = [c_void_p]
    lib.switchtec_fw_part_summary_free.restype = None

    # int switchtec_fw_is_boot_ro(struct switchtec_dev *dev)
    lib.switchtec_fw_is_boot_ro.argtypes = [c_void_p]
    lib.switchtec_fw_is_boot_ro.restype = c_int

    # int switchtec_fw_set_boot_ro(struct switchtec_dev *dev,
    #     enum switchtec_fw_ro ro)
    lib.switchtec_fw_set_boot_ro.argtypes = [c_void_p, c_int]
    lib.switchtec_fw_set_boot_ro.restype = c_int

    # const char *switchtec_fw_image_type(
    #     const struct switchtec_fw_image_info *info)
    lib.switchtec_fw_image_type.argtypes = [POINTER(SwitchtecFwImageInfo)]
    lib.switchtec_fw_image_type.restype = c_char_p


def _setup_bw_lat_functions(lib: ctypes.CDLL) -> None:
    """Bandwidth and latency counter functions."""

    # int switchtec_bwcntr_many(struct switchtec_dev *dev, int nr_ports,
    #     int *phys_port_ids, int clear, struct switchtec_bwcntr_res *res)
    lib.switchtec_bwcntr_many.argtypes = [
        c_void_p,
        c_int,
        POINTER(c_int),
        c_int,
        POINTER(SwitchtecBwCntrRes),
    ]
    lib.switchtec_bwcntr_many.restype = c_int

    # int switchtec_bwcntr_all(struct switchtec_dev *dev, int clear,
    #     struct switchtec_port_id **ports, struct switchtec_bwcntr_res **res)
    lib.switchtec_bwcntr_all.argtypes = [
        c_void_p,
        c_int,
        POINTER(POINTER(SwitchtecPortId)),
        POINTER(POINTER(SwitchtecBwCntrRes)),
    ]
    lib.switchtec_bwcntr_all.restype = c_int

    # int switchtec_lat_setup(struct switchtec_dev *dev, int egress_port_id,
    #     int ingress_port_id, int clear)
    lib.switchtec_lat_setup.argtypes = [c_void_p, c_int, c_int, c_int]
    lib.switchtec_lat_setup.restype = c_int

    # int switchtec_lat_get(struct switchtec_dev *dev, int clear,
    #     int egress_port_ids, int *cur_ns, int *max_ns)
    lib.switchtec_lat_get.argtypes = [c_void_p, c_int, c_int, POINTER(c_int), POINTER(c_int)]
    lib.switchtec_lat_get.restype = c_int


def _setup_diag_functions(lib: ctypes.CDLL) -> None:
    """Diagnostic functions: eye, ltssm, loopback, pattern, rcvr, eq, crosshair."""

    # ── Cross Hair ──
    lib.switchtec_diag_cross_hair_enable.argtypes = [c_void_p, c_int]
    lib.switchtec_diag_cross_hair_enable.restype = c_int

    lib.switchtec_diag_cross_hair_disable.argtypes = [c_void_p]
    lib.switchtec_diag_cross_hair_disable.restype = c_int

    lib.switchtec_diag_cross_hair_get.argtypes = [
        c_void_p,
        c_int,
        c_int,
        POINTER(SwitchtecDiagCrossHair),
    ]
    lib.switchtec_diag_cross_hair_get.restype = c_int

    # ── Eye Diagram ──
    lib.switchtec_diag_eye_set_mode.argtypes = [c_void_p, c_int]
    lib.switchtec_diag_eye_set_mode.restype = c_int

    # int switchtec_diag_eye_start(struct switchtec_dev *dev, int lane_mask[4],
    #     struct range *x_range, struct range *y_range, int step_interval,
    #     int capture_depth, int sar_sel, int intleav_sel, int hstep,
    #     int data_mode, int eye_mode, uint64_t refclk, int vstep)
    lib.switchtec_diag_eye_start.argtypes = [
        c_void_p,
        c_int * 4,
        POINTER(Range),
        POINTER(Range),
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_uint64,
        c_int,
    ]
    lib.switchtec_diag_eye_start.restype = c_int

    # int switchtec_diag_eye_fetch(struct switchtec_dev *dev, double *pixels,
    #     size_t pixel_cnt, int *lane_id)
    lib.switchtec_diag_eye_fetch.argtypes = [c_void_p, POINTER(c_double), c_size_t, POINTER(c_int)]
    lib.switchtec_diag_eye_fetch.restype = c_int

    lib.switchtec_diag_eye_cancel.argtypes = [c_void_p]
    lib.switchtec_diag_eye_cancel.restype = c_int

    # int switchtec_diag_eye_read(struct switchtec_dev *dev, int lane_id,
    #     int bin, int* num_phases, double* ber_data)
    lib.switchtec_diag_eye_read.argtypes = [
        c_void_p,
        c_int,
        c_int,
        POINTER(c_int),
        POINTER(c_double),
    ]
    lib.switchtec_diag_eye_read.restype = c_int

    # ── Loopback ──
    lib.switchtec_diag_loopback_set.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
    ]
    lib.switchtec_diag_loopback_set.restype = c_int

    lib.switchtec_diag_loopback_get.argtypes = [c_void_p, c_int, POINTER(c_int), POINTER(c_int)]
    lib.switchtec_diag_loopback_get.restype = c_int

    # ── Pattern Gen/Mon ──
    lib.switchtec_diag_pattern_gen_set.argtypes = [c_void_p, c_int, c_int, c_int]
    lib.switchtec_diag_pattern_gen_set.restype = c_int

    lib.switchtec_diag_pattern_gen_get.argtypes = [c_void_p, c_int, POINTER(c_int)]
    lib.switchtec_diag_pattern_gen_get.restype = c_int

    lib.switchtec_diag_pattern_mon_set.argtypes = [c_void_p, c_int, c_int]
    lib.switchtec_diag_pattern_mon_set.restype = c_int

    lib.switchtec_diag_pattern_mon_get.argtypes = [
        c_void_p,
        c_int,
        c_int,
        POINTER(c_int),
        POINTER(c_uint64),
    ]
    lib.switchtec_diag_pattern_mon_get.restype = c_int

    lib.switchtec_diag_pattern_inject.argtypes = [c_void_p, c_int, ctypes.c_uint]
    lib.switchtec_diag_pattern_inject.restype = c_int

    # ── Receiver Object ──
    lib.switchtec_diag_rcvr_obj.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        POINTER(SwitchtecRcvrObj),
    ]
    lib.switchtec_diag_rcvr_obj.restype = c_int

    lib.switchtec_diag_rcvr_ext.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        POINTER(SwitchtecRcvrExt),
    ]
    lib.switchtec_diag_rcvr_ext.restype = c_int

    # ── Port EQ ──
    lib.switchtec_diag_port_eq_tx_coeff.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        POINTER(SwitchtecPortEqCoeff),
    ]
    lib.switchtec_diag_port_eq_tx_coeff.restype = c_int

    lib.switchtec_diag_port_eq_tx_table.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        POINTER(SwitchtecPortEqTable),
    ]
    lib.switchtec_diag_port_eq_tx_table.restype = c_int

    lib.switchtec_diag_port_eq_tx_fslf.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        POINTER(SwitchtecPortEqTxFslf),
    ]
    lib.switchtec_diag_port_eq_tx_fslf.restype = c_int

    # ── LTSSM Log ──
    lib.switchtec_diag_ltssm_log.argtypes = [
        c_void_p,
        c_int,
        POINTER(c_int),
        POINTER(SwitchtecDiagLtssmLog),
    ]
    lib.switchtec_diag_ltssm_log.restype = c_int

    lib.switchtec_diag_ltssm_clear.argtypes = [c_void_p, c_int]
    lib.switchtec_diag_ltssm_clear.restype = c_int


def _setup_inject_functions(lib: ctypes.CDLL) -> None:
    """Error injection functions."""

    lib.switchtec_inject_err_dllp.argtypes = [c_void_p, c_int, c_int]
    lib.switchtec_inject_err_dllp.restype = c_int

    lib.switchtec_inject_err_dllp_crc.argtypes = [c_void_p, c_int, c_int, c_uint16]
    lib.switchtec_inject_err_dllp_crc.restype = c_int

    lib.switchtec_inject_err_tlp_lcrc.argtypes = [c_void_p, c_int, c_int, c_uint8]
    lib.switchtec_inject_err_tlp_lcrc.restype = c_int

    lib.switchtec_inject_err_tlp_seq_num.argtypes = [c_void_p, c_int]
    lib.switchtec_inject_err_tlp_seq_num.restype = c_int

    lib.switchtec_inject_err_ack_nack.argtypes = [c_void_p, c_int, c_uint16, c_uint8]
    lib.switchtec_inject_err_ack_nack.restype = c_int

    lib.switchtec_inject_err_cto.argtypes = [c_void_p, c_int]
    lib.switchtec_inject_err_cto.restype = c_int


def _setup_osa_functions(lib: ctypes.CDLL) -> None:
    """Ordered Set Analyzer functions."""

    lib.switchtec_osa.argtypes = [c_void_p, c_int, c_int]
    lib.switchtec_osa.restype = c_int

    lib.switchtec_osa_config_type.argtypes = [c_void_p, c_int, c_int, c_int, c_int, c_int]
    lib.switchtec_osa_config_type.restype = c_int

    lib.switchtec_osa_config_pattern.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        POINTER(c_uint32),
        POINTER(c_uint32),
    ]
    lib.switchtec_osa_config_pattern.restype = c_int

    lib.switchtec_osa_capture_control.argtypes = [
        c_void_p,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
        c_int,
    ]
    lib.switchtec_osa_capture_control.restype = c_int

    lib.switchtec_osa_capture_data.argtypes = [c_void_p, c_int, c_int, c_int]
    lib.switchtec_osa_capture_data.restype = c_int

    lib.switchtec_osa_dump_conf.argtypes = [c_void_p, c_int]
    lib.switchtec_osa_dump_conf.restype = c_int


def _setup_fabric_functions(lib: ctypes.CDLL) -> None:
    """Fabric/topology function prototypes for PAX devices."""

    # int switchtec_topo_info_dump(struct switchtec_dev *dev,
    #     struct switchtec_fab_topo_info *topo_info)
    lib.switchtec_topo_info_dump.argtypes = [c_void_p, c_void_p]
    lib.switchtec_topo_info_dump.restype = c_int

    # int switchtec_fab_port_config_get(struct switchtec_dev *dev,
    #     uint8_t phys_port_id, struct switchtec_fab_port_config *info)
    lib.switchtec_fab_port_config_get.argtypes = [c_void_p, c_uint8, POINTER(SwitchtecFabPortConfig)]
    lib.switchtec_fab_port_config_get.restype = c_int

    # int switchtec_fab_port_config_set(struct switchtec_dev *dev,
    #     uint8_t phys_port_id, struct switchtec_fab_port_config *info)
    lib.switchtec_fab_port_config_set.argtypes = [c_void_p, c_uint8, POINTER(SwitchtecFabPortConfig)]
    lib.switchtec_fab_port_config_set.restype = c_int

    # int switchtec_port_control(struct switchtec_dev *dev,
    #     uint8_t control_type, uint8_t phys_port_id,
    #     uint8_t hot_reset_flag)
    lib.switchtec_port_control.argtypes = [
        c_void_p,
        c_uint8,
        c_uint8,
        c_uint8,
    ]
    lib.switchtec_port_control.restype = c_int

    # int switchtec_gfms_bind(struct switchtec_dev *dev,
    #     struct switchtec_gfms_bind_req *req)
    lib.switchtec_gfms_bind.argtypes = [c_void_p, POINTER(SwitchtecGfmsBindReq)]
    lib.switchtec_gfms_bind.restype = c_int

    # int switchtec_gfms_unbind(struct switchtec_dev *dev,
    #     struct switchtec_gfms_unbind_req *req)
    lib.switchtec_gfms_unbind.argtypes = [c_void_p, POINTER(SwitchtecGfmsUnbindReq)]
    lib.switchtec_gfms_unbind.restype = c_int

    # int switchtec_get_gfms_events(struct switchtec_dev *dev,
    #     struct switchtec_gfms_event *elist, size_t elist_len,
    #     int *overflow, size_t *remain_number)
    lib.switchtec_get_gfms_events.argtypes = [
        c_void_p,
        c_void_p,
        c_size_t,
        POINTER(c_int),
        POINTER(c_size_t),
    ]
    lib.switchtec_get_gfms_events.restype = c_int

    # int switchtec_clear_gfms_events(struct switchtec_dev *dev)
    lib.switchtec_clear_gfms_events.argtypes = [c_void_p]
    lib.switchtec_clear_gfms_events.restype = c_int
