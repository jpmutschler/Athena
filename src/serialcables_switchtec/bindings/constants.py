"""Constants and enumerations from Switchtec C headers.

Maps C #defines and enums to Python IntEnum/IntFlag classes.
"""

from __future__ import annotations

import sys
from enum import IntEnum, IntFlag

# ─── Limits ───────────────────────────────────────────────────────────

MAX_PARTS = 48
MAX_PORTS = 60
MAX_PORTS_GEN6 = 20
MAX_LANES = 100
MAX_LANES_GEN6 = 144
MAX_STACKS = 8
PORTS_PER_STACK = 8
MAX_EVENT_COUNTERS = 64
UNBOUND_PORT = 255
PFF_PORT_VEP = 100
MAX_PFF_CSR = 255

DIAG_MAX_TLP_DWORDS = 132
DIAG_CROSS_HAIR_ALL_LANES = -1
DIAG_CROSS_HAIR_MAX_LANES = 64

LAT_ALL_INGRESS = 63

PATH_MAX = 260 if sys.platform == "win32" else 4096


# ─── PCIe Generation ─────────────────────────────────────────────────


class SwitchtecGen(IntEnum):
    GEN3 = 0
    GEN4 = 1
    GEN5 = 2
    GEN6 = 3
    UNKNOWN = 4


# ─── Device Revision ─────────────────────────────────────────────────


class SwitchtecRev(IntEnum):
    REVA = 0x0F
    REVB = 0x00
    REVC = 0x01
    UNKNOWN = 0xFF


# ─── Boot Phase ──────────────────────────────────────────────────────


class SwitchtecBootPhase(IntEnum):
    BL1 = 1
    BL2 = 2
    FW = 3
    UNKNOWN = 4


# ─── Device Variant ──────────────────────────────────────────────────


class SwitchtecVariant(IntEnum):
    PFX = 0
    PFXL = 1
    PFXI = 2
    PSX = 3
    PAX = 4
    PAXA = 5
    PFXA = 6
    PSXA = 7
    UNKNOWN = 8


# ─── Bandwidth Type ──────────────────────────────────────────────────


class BwType(IntEnum):
    RAW = 0x0
    PAYLOAD = 0x1


# ─── Firmware Type ───────────────────────────────────────────────────


class FwType(IntEnum):
    UNKNOWN = 0
    BOOT = 1
    MAP = 2
    IMG = 3
    CFG = 4
    NVLOG = 5
    SEEPROM = 6
    KEY = 7
    BL2 = 8
    RIOT = 9


# ─── Diagnostic Pattern ─────────────────────────────────────────────


class DiagPattern(IntEnum):
    PRBS_7 = 0
    PRBS_11 = 1
    PRBS_23 = 2
    PRBS_31 = 3
    PRBS_9 = 4
    PRBS_15 = 5
    DISABLED = 6


class DiagPatternGen5(IntEnum):
    PRBS_7 = 0
    PRBS_11 = 1
    PRBS_23 = 2
    PRBS_31 = 3
    PRBS_9 = 4
    PRBS_15 = 5
    PRBS_5 = 6
    PRBS_20 = 7
    DISABLED = 10


class DiagPatternGen6(IntEnum):
    PRBS_7 = 0
    PRBS_9 = 1
    PRBS_11 = 2
    PRBS_13 = 3
    PRBS_15 = 4
    PRBS_23 = 5
    PRBS_31 = 6
    PCIE_52_UI_JIT = 0x19
    DISABLED = 0x1A


# ─── Diagnostic Pattern Link Rate ───────────────────────────────────


class DiagPatternLinkRate(IntEnum):
    DISABLED = 0
    GEN1 = 1
    GEN2 = 2
    GEN3 = 3
    GEN4 = 4
    GEN5 = 5
    GEN6 = 6


# ─── Diagnostic Cross Hair State ────────────────────────────────────


class DiagCrossHairState(IntEnum):
    DISABLED = 0
    RESVD = 1
    WAITING = 2
    FIRST_ERROR_RIGHT = 3
    ERROR_FREE_RIGHT = 4
    FINAL_RIGHT = 5
    FIRST_ERROR_LEFT = 6
    ERROR_FREE_LEFT = 7
    FINAL_LEFT = 8
    FIRST_ERROR_TOP_RIGHT = 9
    ERROR_FREE_TOP_RIGHT = 10
    FINAL_TOP_RIGHT = 11
    FIRST_ERROR_BOT_RIGHT = 12
    ERROR_FREE_BOT_RIGHT = 13
    FINAL_BOT_RIGHT = 14
    FIRST_ERROR_TOP_LEFT = 15
    ERROR_FREE_TOP_LEFT = 16
    FINAL_TOP_LEFT = 17
    FIRST_ERROR_BOT_LEFT = 18
    ERROR_FREE_BOT_LEFT = 19
    FINAL_BOT_LEFT = 20
    DONE = 21
    ERROR = 22


# ─── Diagnostic Loopback ────────────────────────────────────────────


class DiagLoopbackEnable(IntFlag):
    RX_TO_TX = 1 << 0
    TX_TO_RX = 1 << 1
    LTSSM = 1 << 2
    PIPE = 1 << 3


class DiagLtssmSpeed(IntEnum):
    GEN1 = 0
    GEN2 = 1
    GEN3 = 2
    GEN4 = 3
    GEN5 = 4
    GEN6 = 5


# ─── Diagnostic End / Link ──────────────────────────────────────────


class DiagEnd(IntEnum):
    LOCAL = 0
    FAR_END = 1


class DiagLink(IntEnum):
    CURRENT = 0
    PREVIOUS = 1


# ─── Eye Data Mode ──────────────────────────────────────────────────


class DiagEyeDataMode(IntEnum):
    RAW = 0
    RATIO = 1


class DiagEyeDataModeGen6(IntEnum):
    ADC = 0
    FFE = 1
    DFE = 2


class DiagEyeModeGen6(IntEnum):
    FULL = 0
    INTERLEAVE = 1
    SAR = 2


class DiagEyeHStep(IntEnum):
    ULTRA_FINE = 1
    FINE = 2
    MEDIUM = 3
    COARSE = 4


# ─── Gen5 Eye Status ────────────────────────────────────────────────


class Gen5DiagEyeStatus(IntEnum):
    IDLE = 0
    PENDING = 1
    IN_PROGRESS = 2
    DONE = 3
    TIMEOUT = 4
    ERROR = 5


# ─── Event ID ────────────────────────────────────────────────────────


class EventId(IntEnum):
    INVALID = -1
    GLOBAL_STACK_ERROR = 0
    GLOBAL_PPU_ERROR = 1
    GLOBAL_ISP_ERROR = 2
    GLOBAL_SYS_RESET = 3
    GLOBAL_FW_EXC = 4
    GLOBAL_FW_NMI = 5
    GLOBAL_FW_NON_FATAL = 6
    GLOBAL_FW_FATAL = 7
    GLOBAL_TWI_MRPC_COMP = 8
    GLOBAL_TWI_MRPC_COMP_ASYNC = 9
    GLOBAL_CLI_MRPC_COMP = 10
    GLOBAL_CLI_MRPC_COMP_ASYNC = 11
    GLOBAL_GPIO_INT = 12
    GLOBAL_GFMS = 13
    PART_PART_RESET = 14
    PART_MRPC_COMP = 15
    PART_MRPC_COMP_ASYNC = 16
    PART_DYN_PART_BIND_COMP = 17
    PFF_AER_IN_P2P = 18
    PFF_AER_IN_VEP = 19
    PFF_DPC = 20
    PFF_CTS = 21
    PFF_UEC = 22
    PFF_HOTPLUG = 23
    PFF_IER = 24
    PFF_THRESH = 25
    PFF_POWER_MGMT = 26
    PFF_TLP_THROTTLING = 27
    PFF_FORCE_SPEED = 28
    PFF_CREDIT_TIMEOUT = 29
    PFF_LINK_STATE = 30
    MAX_EVENTS = 31


# ─── Event Flags ─────────────────────────────────────────────────────


class EventFlags(IntFlag):
    CLEAR = 1 << 0
    EN_POLL = 1 << 1
    EN_LOG = 1 << 2
    EN_CLI = 1 << 3
    EN_FATAL = 1 << 4
    DIS_POLL = 1 << 5
    DIS_LOG = 1 << 6
    DIS_CLI = 1 << 7
    DIS_FATAL = 1 << 8


# ─── Link Rate Enum ─────────────────────────────────────────────────


class LinkRate(IntEnum):
    INVALID = 0
    GEN1 = 1
    GEN2 = 2
    GEN3 = 3
    GEN4 = 4
    GEN5 = 5
    GEN6 = 6


# ─── Lane EQ Dump Type ──────────────────────────────────────────────


class LaneEqDumpType(IntEnum):
    CURRENT = 0
    PREVIOUS = 1


# ─── LTSSM string lookup tables ─────────────────────────────────────
# These are static inline functions in the C headers, not exported from
# the shared library, so we reimplement them as Python dicts.

LTSSM_STRINGS_GEN4: dict[int, str] = {
    0x0000: "Detect (INACTIVE)",
    0x0100: "Detect (QUIET)",
    0x0200: "Detect (SPD_CHD0)",
    0x0300: "Detect (SPD_CHD1)",
    0x0400: "Detect (ACTIVE0)",
    0x0500: "Detect (ACTIVE1)",
    0x0600: "Detect (P1_TO_P0)",
    0x0700: "Detect (P0_TO_P1_0)",
    0x0800: "Detect (P0_TO_P1_1)",
    0x0900: "Detect (P0_TO_P1_2)",
    0xFF00: "Detect",
    0x0001: "Polling (INACTIVE)",
    0x0101: "Polling (ACTIVE_ENTRY)",
    0x0201: "Polling (ACTIVE)",
    0x0301: "Polling (CFG)",
    0x0401: "Polling (COMP)",
    0x0501: "Polling (COMP_ENTRY)",
    0x0601: "Polling (COMP_EIOS)",
    0x0701: "Polling (COMP_EIOS_ACK)",
    0x0801: "Polling (COMP_IDLE)",
    0xFF01: "Polling",
    0x0002: "Config (INACTIVE)",
    0x0102: "Config (US_LW_START)",
    0x0202: "Config (US_LW_ACCEPT)",
    0x0302: "Config (US_LN_WAIT)",
    0x0402: "Config (US_LN_ACCEPT)",
    0x0502: "Config (DS_LW_START)",
    0x0602: "Config (DS_LW_ACCEPT)",
    0x0702: "Config (DS_LN_WAIT)",
    0x0802: "Config (DS_LN_ACCEPT)",
    0x0902: "Config (COMPLETE)",
    0x0A02: "Config (IDLE)",
    0xFF02: "Config",
    0x0003: "L0 (INACTIVE)",
    0x0103: "L0 (L0)",
    0x0203: "L0 (TX_EL_IDLE)",
    0x0303: "L0 (TX_IDLE_MIN)",
    0xFF03: "L0",
    0x0004: "Recovery (INACTIVE)",
    0x0104: "Recovery (RCVR_LOCK)",
    0x0204: "Recovery (RCVR_CFG)",
    0x0304: "Recovery (IDLE)",
    0x0404: "Recovery (SPEED0)",
    0x0504: "Recovery (SPEED1)",
    0x0604: "Recovery (SPEED2)",
    0x0704: "Recovery (SPEED3)",
    0x0804: "Recovery (EQ_PH0)",
    0x0904: "Recovery (EQ_PH1)",
    0x0A04: "Recovery (EQ_PH2)",
    0x0B04: "Recovery (EQ_PH3)",
    0xFF04: "Recovery",
    0x0005: "Disable (INACTIVE)",
    0x0105: "Disable (DISABLE0)",
    0x0205: "Disable (DISABLE1)",
    0x0305: "Disable (DISABLE2)",
    0x0405: "Disable (DISABLE3)",
    0xFF05: "Disable",
    0x0006: "Loop Back (INACTIVE)",
    0x0106: "Loop Back (ENTRY)",
    0x0206: "Loop Back (ENTRY_EXIT)",
    0x0306: "Loop Back (EIOS)",
    0x0406: "Loop Back (EIOS_ACK)",
    0x0506: "Loop Back (IDLE)",
    0x0606: "Loop Back (ACTIVE)",
    0x0706: "Loop Back (EXIT0)",
    0x0806: "Loop Back (EXIT1)",
    0xFF06: "Loop Back",
    0x0007: "Hot Reset (INACTIVE)",
    0x0107: "Hot Reset (HOT_RESET)",
    0x0207: "Hot Reset (MASTER_UP)",
    0x0307: "Hot Reset (MASTER_DOWN)",
    0xFF07: "Hot Reset",
    0x0008: "TxL0s (INACTIVE)",
    0x0108: "TxL0s (IDLE)",
    0x0208: "TxL0s (T0_L0)",
    0x0308: "TxL0s (FTS0)",
    0x0408: "TxL0s (FTS1)",
    0xFF08: "TxL0s",
    0x0009: "L1 (INACTIVE)",
    0x0109: "L1 (IDLE)",
    0x0209: "L1 (SUBSTATE)",
    0x0309: "L1 (SPD_CHG1)",
    0x0409: "L1 (T0_L0)",
    0xFF09: "L1",
    0x000A: "L2 (INACTIVE)",
    0x010A: "L2 (IDLE)",
    0x020A: "L2 (TX_WAKE0)",
    0x030A: "L2 (TX_WAKE1)",
    0x040A: "L2 (EXIT)",
    0x050A: "L2 (SPEED)",
    0xFF0A: "L2",
}

LTSSM_STRINGS_GEN5: dict[int, str] = {
    0x0000: "Detect (INACTIVE)",
    0x0100: "Detect (QUIET)",
    0x0200: "Detect (SPD_CHG0)",
    0x0300: "Detect (SPD_CHG1)",
    0x0400: "Detect (ACTIVE0)",
    0x0500: "Detect (ACTIVE1)",
    0x0600: "Detect (ACTIVE2)",
    0x0700: "Detect (P1_TO_P0)",
    0x0800: "Detect (P0_TO_P1_0)",
    0x0900: "Detect (P0_TO_P1_1)",
    0x0A00: "Detect (P0_TO_P1_2)",
    0xFF00: "Detect",
    0x0001: "Polling (INACTIVE)",
    0x0101: "Polling (ACTIVE_ENTRY)",
    0x0201: "Polling (ACTIVE)",
    0x0301: "Polling (CFG)",
    0x0401: "Polling (COMP)",
    0x0501: "Polling (COMP_ENTRY)",
    0x0601: "Polling (COMP_EIOS)",
    0x0701: "Polling (COMP_EIOS_ACK)",
    0x0801: "Polling (COMP_IDLE)",
    0xFF01: "Polling",
    0x0002: "Config (INACTIVE)",
    0x0102: "Config (US_LW_START)",
    0x0202: "Config (US_LW_ACCEPT)",
    0x0302: "Config (US_LN_WAIT)",
    0x0402: "Config (US_LN_ACCEPT)",
    0x0502: "Config (DS_LW_START)",
    0x0602: "Config (DS_LW_ACCEPT)",
    0x0702: "Config (DS_LN_WAIT)",
    0x0802: "Config (DS_LN_ACCEPT)",
    0x0902: "Config (COMPLETE)",
    0x0A02: "Config (IDLE)",
    0xFF02: "Config",
    0x0003: "L0 (INACTIVE)",
    0x0103: "L0 (L0)",
    0x0203: "L0 (TX_EL_IDLE)",
    0x0303: "L0 (TX_IDLE_MIN)",
    0xFF03: "L0",
    0x0004: "Recovery (INACTIVE)",
    0x0104: "Recovery (RCVR_LOCK)",
    0x0204: "Recovery (RCVR_CFG)",
    0x0304: "Recovery (IDLE)",
    0x0404: "Recovery (SPEED0)",
    0x0504: "Recovery (SPEED1)",
    0x0604: "Recovery (SPEED2)",
    0x0704: "Recovery (SPEED3)",
    0x0804: "Recovery (EQ_PH0)",
    0x0904: "Recovery (EQ_PH1)",
    0x0A04: "Recovery (EQ_PH2)",
    0x0B04: "Recovery (EQ_PH3)",
    0xFF04: "Recovery",
    0x0005: "Disable (INACTIVE)",
    0x0105: "Disable (DISABLE0)",
    0x0205: "Disable (DISABLE1)",
    0x0305: "Disable (DISABLE2)",
    0x0405: "Disable (DISABLE3)",
    0xFF05: "Disable",
    0x0006: "Loop Back (INACTIVE)",
    0x0106: "Loop Back (ENTRY)",
    0x0206: "Loop Back (ENTRY_EXIT)",
    0x0306: "Loop Back (EIOS)",
    0x0406: "Loop Back (EIOS_ACK)",
    0x0506: "Loop Back (IDLE)",
    0x0606: "Loop Back (ACTIVE)",
    0x0706: "Loop Back (EXIT0)",
    0x0806: "Loop Back (EXIT1)",
    0xFF06: "Loop Back",
    0x0007: "Hot Reset (INACTIVE)",
    0x0107: "Hot Reset (HOT_RESET)",
    0x0207: "Hot Reset (MASTER_UP)",
    0x0307: "Hot Reset (MASTER_DOWN)",
    0xFF07: "Hot Reset",
    0x0008: "TxL0s (INACTIVE)",
    0x0108: "TxL0s (IDLE)",
    0x0208: "TxL0s (T0_L0)",
    0x0308: "TxL0s (FTS0)",
    0x0408: "TxL0s (FTS1)",
    0xFF08: "TxL0s",
    0x0009: "L1 (INACTIVE)",
    0x0109: "L1 (IDLE)",
    0x0209: "L1 (SUBSTATE)",
    0x0309: "L1 (TO_L0)",
    0xFF09: "L1",
    0x000A: "L2 (INACTIVE)",
    0x010A: "L2 (IDLE)",
    0x020A: "L2 (TX_WAKE0)",
    0x030A: "L2 (TX_WAKE1)",
    0x040A: "L2 (EXIT)",
    0x050A: "L2 (SPEED)",
    0xFF0A: "L2",
}

LTSSM_STRINGS_GEN6: dict[int, str] = {
    0x00: "Detect (QUIET)",
    0x01: "Detect (ACTIVE)",
    0x02: "Polling (ACTIVE)",
    0x03: "Polling (COMPLIANCE)",
    0x04: "Polling (CONFIG)",
    0x05: "Detect (PRE_DETECT_QUIET)",
    0x06: "Detect (DETECT_WAIT)",
    0x07: "Configuration (LINKWD_START)",
    0x08: "Configuration (LINKWD_ACCEPT)",
    0x09: "Configuration (LANENUM_WAIT)",
    0x0A: "Configuration (LANENUM_ACCEPT)",
    0x0B: "Configuration (COMPLETE)",
    0x0C: "Configuration (IDLE)",
    0x0D: "Recovery (LOCK)",
    0x0E: "Recovery (SPEED)",
    0x0F: "Recovery (RCVRCFG)",
    0x10: "Recovery (IDLE)",
    0x11: "L0 (ACTIVE)",
    0x12: "L0s (IDLE)",
    0x13: "L1/L2/L3 (SEND_EIDLE)",
    0x14: "L1 (IDLE)",
    0x15: "L2 (IDLE)",
    0x16: "L2 (WAKE)",
    0x17: "Disabled (ENTRY)",
    0x18: "Disabled (IDLE)",
    0x19: "Disabled",
    0x1A: "Loopback (ENTRY)",
    0x1B: "Loopback (ACTIVE)",
    0x1C: "Loopback (EXIT)",
    0x1D: "Loopback (EXIT_TIMEOUT)",
    0x1E: "Hot Reset (ENTRY)",
    0x1F: "Hot Reset",
    0x20: "Recovery (EQ0)",
    0x21: "Recovery (EQ1)",
    0x22: "Recovery (EQ2)",
    0x23: "Recovery (EQ3)",
}


def ltssm_str(ltssm: int, gen: SwitchtecGen, show_minor: bool = True) -> str:
    """Get LTSSM state string for a given LTSSM value and generation."""
    if gen == SwitchtecGen.GEN6:
        return LTSSM_STRINGS_GEN6.get(ltssm, "UNKNOWN")

    table = LTSSM_STRINGS_GEN5 if gen == SwitchtecGen.GEN5 else LTSSM_STRINGS_GEN4
    if not show_minor:
        ltssm |= 0xFF00
    return table.get(ltssm, "UNKNOWN")


# ─── Link rate data tables ──────────────────────────────────────────

GEN_TRANSFERS = [0.0, 2.5, 5.0, 8.0, 16.0, 32.0, 64.0]
GEN_DATARATE = [0.0, 250.0, 500.0, 985.0, 1969.0, 3938.0, 7877.0]


# ─── Firmware Download Status ─────────────────────────────────────


class FwDlStatus(IntEnum):
    """Firmware download status codes."""

    READY = 0
    INPROGRESS = 1
    ERROR = 2
    COMPLETE = 3


# ─── Firmware Read-Only Flag ──────────────────────────────────────


class FwRo(IntEnum):
    """Firmware read-only flags."""

    RW = 0
    RO = 1


# ─── Event Counter Type Masks ────────────────────────────────────────


class EvCntrTypeMask(IntFlag):
    """Event counter type mask (may be OR'd together).

    Aggregate masks:
        ALL_ERRORS -- bits 0-18 (19 error types, excludes RULE_TABLE_HIT and TLP counters)
        ALL_TLPS   -- bits 20-22 (POSTED_TLP | COMP_TLP | NON_POSTED_TLP)
        ALL        -- bits 0-22 (all error types + rule table + TLP counters)
    """

    UNSUP_REQ_ERR = 1 << 0
    ECRC_ERR = 1 << 1
    MALFORM_TLP_ERR = 1 << 2
    RCVR_OFLOW_ERR = 1 << 3
    CMPLTR_ABORT_ERR = 1 << 4
    POISONED_TLP_ERR = 1 << 5
    SURPRISE_DOWN_ERR = 1 << 6
    DATA_LINK_PROTO_ERR = 1 << 7
    HDR_LOG_OFLOW_ERR = 1 << 8
    UNCOR_INT_ERR = 1 << 9
    REPLAY_TMR_TIMEOUT = 1 << 10
    REPLAY_NUM_ROLLOVER = 1 << 11
    BAD_DLLP = 1 << 12
    BAD_TLP = 1 << 13
    RCVR_ERR = 1 << 14
    RCV_FATAL_MSG = 1 << 15
    RCV_NON_FATAL_MSG = 1 << 16
    RCV_CORR_MSG = 1 << 17
    NAK_RCVD = 1 << 18
    RULE_TABLE_HIT = 1 << 19
    POSTED_TLP = 1 << 20
    COMP_TLP = 1 << 21
    NON_POSTED_TLP = 1 << 22
    ALL_ERRORS = (1 << 19) - 1
    ALL_TLPS = (1 << 20) | (1 << 21) | (1 << 22)
    ALL = (1 << 23) - 1


# ─── Fabric Port Control ────────────────────────────────────────────


class FabPortControlType(IntEnum):
    """Fabric port control operations."""

    DISABLE = 0
    ENABLE = 1
    HOT_RESET = 2


class FabHotResetFlag(IntEnum):
    """Hot reset flags for fabric port control."""

    NONE = 0
    PERST = 1
