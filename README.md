# Athena -- serialcables-switchtec

<!-- Badges -->
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Build](https://img.shields.io/badge/build-hatchling-green.svg)](https://hatch.pypa.io/)
<!-- [![PyPI version](https://img.shields.io/pypi/v/serialcables-switchtec.svg)](https://pypi.org/project/serialcables-switchtec/) -->
<!-- [![CI](https://github.com/serialcables/serialcables-switchtec/actions/workflows/ci.yml/badge.svg)](https://github.com/serialcables/serialcables-switchtec/actions) -->
<!-- [![Coverage](https://img.shields.io/codecov/c/github/serialcables/serialcables-switchtec.svg)](https://codecov.io/gh/serialcables/serialcables-switchtec) -->

**Athena** is a Python-friendly interface to the Microsemi/Microchip Switchtec PCIe switch management library (`switchtec-user` 4.4-rc2, 200+ API functions). Built for **PCIe Validation Engineers** who perform eye diagrams, LTSSM analysis, loopback testing, pattern generation and monitoring, error injection, and receiver characterization.

Developed by [Serial Cables](https://www.serialcables.com/), a manufacturer of PCIe test equipment and interposer solutions.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [REST API](#rest-api)
- [Browser Dashboard](#browser-dashboard)
- [Python Library Usage](#python-library-usage)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Testing](#testing)
- [Development Status](#development-status)
- [License](#license)

---

## Features

**ctypes Bindings Layer** -- Zero-dependency wrapping of the Switchtec C shared library with platform-aware loading (Linux `.so`, Windows `.dll`). Provides typed function prototypes, C struct definitions, and IntEnum constants mapped directly from C headers.

**Click CLI** (`athena`) -- Full-featured command-line interface with human-readable output, `--json-output` mode for scripting, and `--debug` logging. Covers device discovery, port status, diagnostics, and error injection.

**FastAPI REST API** -- Async HTTP API with auto-generated OpenAPI documentation, API key authentication, input validation via Pydantic, WebSocket support for streaming diagnostics, and restricted CORS.

**NiceGUI Browser Dashboard** -- Dark-themed browser UI with Serial Cables branding. Provides real-time device cards, port grids, eye diagram charts, LTSSM timeline visualization, and performance monitoring.

**Diagnostics Suite** -- Comprehensive PCIe validation tooling:

| Capability | Description |
|---|---|
| Eye Diagrams | BER eye capture with configurable step size and lane selection |
| LTSSM Analysis | State machine log capture, decode, and clear (Gen3/4/5/6 tables) |
| Loopback Testing | RX-to-TX, TX-to-RX, LTSSM, and PIPE loopback modes |
| Pattern Gen/Mon | PRBS7/9/11/15/23/31 pattern generation and bit-error monitoring |
| Error Injection | DLLP, DLLP CRC, TLP LCRC, sequence number, ACK/NACK, completion timeout |
| Receiver Characterization | CTLE, target amplitude, speculative DFE, dynamic DFE readout |
| Port Equalization | TX coefficient dump (local/far-end, current/previous link) |
| Cross-Hair Analysis | Per-lane eye limit measurement with enable/disable/get control |
| Ordered Set Analysis | Type/pattern configuration and capture control |

**Security** -- API key authentication via `SWITCHTEC_API_KEY` environment variable, localhost-only binding by default, restricted CORS origins, and Pydantic input validation on all API endpoints.

---

## Architecture

```
NiceGUI Dashboard / Click CLI
            |
    FastAPI REST + WebSocket API
            |
    Core Domain Layer (Python)
            |
    ctypes Bindings Layer
            |
    libswitchtec.so / switchtec.dll
```

Each layer has a single responsibility:

- **CLI / UI** -- User-facing interfaces. The CLI outputs human-readable text or JSON. The dashboard renders live charts and tables.
- **REST API** -- Stateless HTTP endpoints with an async device registry, input validation, and structured error responses.
- **Core Domain** -- Business logic classes (`SwitchtecDevice`, `DiagnosticsManager`, `ErrorInjector`, `OrderedSetAnalyzer`, `PerformanceMonitor`) that wrap C library calls and return immutable Pydantic models.
- **Bindings** -- Platform-aware CDLL loader, ctypes `Structure` definitions matching C structs, function prototypes with `argtypes`/`restype`, and IntEnum constants from C headers.

---

## Prerequisites

### Python

Python 3.10 or later is required.

### Switchtec C Library

This package wraps the [Microchip switchtec-user](https://github.com/Microsemi/switchtec-user) C library. You must provide a compiled copy of `libswitchtec.so` (Linux) or `switchtec.dll` (Windows).

The library loader searches the following locations in order:

1. `vendor/switchtec/` relative to the package installation (vendored build)
2. The path specified by the `SWITCHTEC_LIB_DIR` environment variable
3. System library paths (`/usr/local/lib`, `/usr/lib`, `/usr/lib64`, `/opt/switchtec/lib`)
4. System `LD_LIBRARY_PATH` / `PATH` fallback

**Building from source (Linux):**

```bash
git clone https://github.com/Microsemi/switchtec-user.git
cd switchtec-user
git checkout v4.4-rc2
./configure --prefix=/usr/local
make
sudo make install
```

**Using a custom path:**

```bash
export SWITCHTEC_LIB_DIR=/path/to/your/built/lib
```

### Hardware

A Microsemi/Microchip Switchtec PCIe switch device must be accessible at a device path such as `/dev/switchtec0` (Linux) or `\\.\switchtec0` (Windows). Appropriate permissions or elevated access may be required.

---

## Installation

**Core only** (CLI + Python library, no server dependencies):

```bash
pip install serialcables-switchtec
```

**With REST API** (adds FastAPI, Uvicorn, WebSockets):

```bash
pip install "serialcables-switchtec[api]"
```

**With browser dashboard** (adds NiceGUI):

```bash
pip install "serialcables-switchtec[ui]"
```

**Everything** (API + UI):

```bash
pip install "serialcables-switchtec[all]"
```

**Development** (adds pytest, ruff, httpx, pytest-asyncio, pytest-cov):

```bash
pip install "serialcables-switchtec[dev]"
```

### From source

```bash
git clone https://github.com/serialcables/serialcables-switchtec.git
cd serialcables-switchtec
pip install -e ".[dev,all]"
```

---

## Quick Start

### 1. Verify library loading

```bash
athena --version
```

### 2. Discover devices

```bash
athena device list
```

```
  switchtec0: Microsemi PSX 48xG4 (/dev/switchtec0)
```

### 3. Read device information

```bash
athena device info /dev/switchtec0
```

```
Name:        switchtec0
Device ID:   0x8572
Generation:  GEN4
Variant:     PSX
Boot Phase:  Main Firmware
FW Version:  4.40 B472
Temperature: 51.2 C
Ports:       48
```

### 4. Start the API server and dashboard

```bash
pip install "serialcables-switchtec[all]"
athena serve
```

Open `http://127.0.0.1:8000` in a browser for the NiceGUI dashboard. API documentation is available at `http://127.0.0.1:8000/docs`.

---

## CLI Reference

The CLI entry point is `athena`. All commands support `--debug` for verbose logging and `--json-output` for machine-readable output.

```bash
athena --help
```

### Global Options

| Flag | Description |
|---|---|
| `--debug` | Enable debug-level structured logging |
| `--json-output` | Format all output as JSON |
| `--version` | Print the package version and exit |

### Device Commands

```bash
# List all Switchtec devices
athena device list

# Show detailed device information
athena device info /dev/switchtec0

# Read die temperature
athena device temp /dev/switchtec0

# Show port status table
athena device status /dev/switchtec0
```

Port status output:

```
  Port   Link  Width   Rate                          LTSSM
------------------------------------------------------------
     0     UP     x4  Gen4                      L0 (L0)
     1   DOWN     x0  Gen1          Detect (INACTIVE)
```

### Diagnostics Commands

**Eye diagram:**

```bash
athena diag eye /dev/switchtec0 --lanes 1,0,0,0 --x-step 1 --y-step 2
```

**LTSSM log:**

```bash
# Dump LTSSM state log for port 0
athena diag ltssm /dev/switchtec0 0

# Clear LTSSM log
athena diag ltssm-clear /dev/switchtec0 0
```

**Loopback:**

```bash
# Enable loopback at Gen4 speed on port 0
athena diag loopback /dev/switchtec0 0 --enable --ltssm-speed gen4

# Disable loopback
athena diag loopback /dev/switchtec0 0 --disable
```

**Pattern generation and monitoring:**

```bash
# Set PRBS31 pattern generator at Gen4 on port 0
athena diag patgen /dev/switchtec0 0 --pattern prbs31 --speed gen4

# Read pattern monitor results for port 0, lane 0
athena diag patmon /dev/switchtec0 0 0
```

**Receiver characterization:**

```bash
# Dump receiver calibration object for port 0, lane 0
athena diag rcvr /dev/switchtec0 0 0 --link current
```

**Port equalization:**

```bash
# Dump TX coefficients for port 0 (local end, current link)
athena diag eq /dev/switchtec0 0 --end local --link current
```

**Cross-hair measurement:**

```bash
# Enable cross-hair on lane 0
athena diag crosshair /dev/switchtec0 --lane 0 --action enable

# Get cross-hair results for all lanes
athena diag crosshair /dev/switchtec0 --action get

# Disable cross-hair
athena diag crosshair /dev/switchtec0 --action disable
```

### Error Injection Commands

All error injection commands are under `athena diag inject`.

```bash
# Inject a raw DLLP on port 0
athena diag inject dllp /dev/switchtec0 0 --data 0xDEAD

# Enable DLLP CRC error injection
athena diag inject dllp-crc /dev/switchtec0 0 --enable --rate 1

# Enable TLP LCRC error injection
athena diag inject tlp-lcrc /dev/switchtec0 0 --enable --rate 1

# Inject TLP sequence number error
athena diag inject seq-num /dev/switchtec0 0

# Inject ACK/NACK errors
athena diag inject ack-nack /dev/switchtec0 0 --seq-num 42 --count 5

# Inject completion timeout
athena diag inject cto /dev/switchtec0 0
```

### Server Command

```bash
# Start API + dashboard on default host/port (127.0.0.1:8000)
athena serve

# Bind to all interfaces on a custom port
athena serve --host 0.0.0.0 --port 9000
```

---

## REST API

The REST API is a FastAPI application with auto-generated OpenAPI documentation at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Authentication

Set the `SWITCHTEC_API_KEY` environment variable before starting the server. All API requests must include the key in the `X-API-Key` header.

```bash
export SWITCHTEC_API_KEY="your-secret-key"
athena serve
```

```bash
curl -H "X-API-Key: your-secret-key" http://127.0.0.1:8000/api/devices/
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (no auth required) |
| `GET` | `/api/devices/` | List managed device sessions |
| `POST` | `/api/devices/{id}/open` | Open a device by path |
| `DELETE` | `/api/devices/{id}` | Close a device session |
| `GET` | `/api/devices/{id}/temperature` | Read die temperature |
| `GET` | `/api/devices/{id}/ports` | List port status |
| `POST` | `/api/devices/{id}/diag/eye/start` | Start eye diagram capture |
| `GET` | `/api/devices/{id}/diag/ltssm` | Dump LTSSM state log |
| `POST` | `/api/devices/{id}/diag/inject/dllp` | Inject DLLP error |

All endpoints return JSON. Error responses follow a consistent structure:

```json
{
  "detail": "Device not found",
  "error_code": 19
}
```

### WebSocket Streams

The API supports WebSocket connections for streaming long-running diagnostic data such as eye diagram progress and real-time LTSSM state changes.

---

## Browser Dashboard

The Athena NiceGUI dashboard provides a browser-based interface for device management and diagnostics, branded with the Serial Cables logo. It starts automatically with `athena serve`.

**Pages:**

| Page | Description |
|---|---|
| Discovery | Scan and connect to Switchtec devices |
| Dashboard | Overview cards showing device health and summary |
| Ports | Port status grid with link state indicators |
| Eye Diagram | Interactive eye diagram chart with capture controls |
| LTSSM Trace | Timeline visualization of LTSSM state transitions |
| Performance | Bandwidth and latency counter display |

**Visual components:** device cards, port grids, eye diagram charts, and LTSSM timeline widgets. Dark theme with Serial Cables branding.

---

## Python Library Usage

### Device Management

```python
from serialcables_switchtec.core.device import SwitchtecDevice

# Open a device as a context manager (auto-closes on exit)
with SwitchtecDevice.open("/dev/switchtec0") as dev:
    print(f"Temperature: {dev.die_temperature:.1f} C")
    print(f"Firmware:    {dev.get_fw_version()}")
    print(f"Generation:  {dev.generation_str}")
    print(f"Variant:     {dev.variant_str}")

    # Get a full device summary
    summary = dev.get_summary()
    print(f"Ports: {summary.port_count}")

    # List port status
    for port in dev.get_status():
        print(f"  Port {port.port.phys_id}: {'UP' if port.link_up else 'DOWN'}")
```

### Device Discovery

```python
from serialcables_switchtec.core.device import SwitchtecDevice

devices = SwitchtecDevice.list_devices()
for d in devices:
    print(f"{d.name}: {d.description} ({d.path})")
```

### Diagnostics

```python
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.diagnostics import DiagnosticsManager
from serialcables_switchtec.bindings.constants import (
    DiagPattern,
    DiagPatternLinkRate,
    DiagLink,
)

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    diag = DiagnosticsManager(dev)

    # Start an eye diagram capture
    diag.eye_start(lane_mask=[1, 0, 0, 0], x_step=1, y_step=2)

    # Dump LTSSM log for port 0
    for entry in diag.ltssm_log(port_id=0):
        print(f"[{entry.timestamp}] {entry.link_state_str}")

    # Set PRBS31 pattern generator at Gen4
    diag.pattern_gen_set(
        port_id=0,
        pattern=DiagPattern.PRBS_31,
        link_speed=DiagPatternLinkRate.GEN4,
    )

    # Read pattern monitor results
    result = diag.pattern_mon_get(port_id=0, lane_id=0)
    print(f"Errors: {result.error_count}")

    # Read receiver calibration
    rcvr = diag.rcvr_obj(port_id=0, lane_id=0, link=DiagLink.CURRENT)
    print(f"CTLE: {rcvr.ctle}")
```

### Error Injection

```python
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.error_injection import ErrorInjector

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    injector = ErrorInjector(dev)

    # Enable DLLP CRC error injection on port 0
    injector.inject_dllp_crc(port_id=0, enable=True, rate=1)

    # Inject a TLP sequence number error
    injector.inject_tlp_seq_num(port_id=0)

    # Inject completion timeout
    injector.inject_cto(port_id=0)
```

### Error Handling

All library errors raise from a single `SwitchtecError` base class. Specific subclasses map to errno values and MRPC return codes from the C library.

```python
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import (
    SwitchtecError,
    DeviceNotFoundError,
    DeviceOpenError,
    LibraryLoadError,
    MrpcError,
    SwitchtecPermissionError,
)

try:
    with SwitchtecDevice.open("/dev/switchtec99") as dev:
        pass
except DeviceNotFoundError as e:
    print(f"Device not found: {e} (errno={e.error_code})")
except LibraryLoadError as e:
    print(f"C library not available: {e}")
except SwitchtecError as e:
    print(f"Unexpected error: {e}")
```

Exception hierarchy:

```
SwitchtecError
  +-- LibraryLoadError
  +-- DeviceNotFoundError
  +-- DeviceOpenError
  +-- InvalidPortError
  +-- InvalidLaneError
  +-- MrpcError
  +-- SwitchtecTimeoutError
  +-- SwitchtecPermissionError
  +-- UnsupportedError
  +-- InvalidParameterError
```

---

## Project Structure

```
src/serialcables_switchtec/
|-- __init__.py                 # Package entry point, exports SwitchtecError
|-- exceptions.py               # Exception hierarchy with errno/MRPC mapping
|
|-- bindings/                   # ctypes interface to libswitchtec
|   |-- library.py              # Platform-aware CDLL loader
|   |-- constants.py            # IntEnums from C headers (Gen, Variant, LTSSM, patterns)
|   |-- types.py                # ctypes Structure definitions matching C structs
|   +-- functions.py            # Function prototypes (argtypes/restype)
|
|-- core/                       # Business logic wrapping C library calls
|   |-- device.py               # SwitchtecDevice: open/close/list/status/temp/fw_version
|   |-- diagnostics.py          # DiagnosticsManager: eye, LTSSM, loopback, pattern, EQ
|   |-- error_injection.py      # ErrorInjector: DLLP, TLP LCRC, seq num, ACK/NACK, CTO
|   |-- osa.py                  # OrderedSetAnalyzer: type/pattern config, capture control
|   +-- performance.py          # PerformanceMonitor: bandwidth counters, latency
|
|-- models/                     # Pydantic models (frozen, immutable)
|   |-- device.py               # DeviceInfo, PortId, PortStatus, DeviceSummary
|   |-- diagnostics.py          # EyeData, LtssmLogEntry, CrossHairResult, ReceiverObject
|   |-- performance.py          # BwCounterResult, LatencyResult, EventCounterResult
|   +-- firmware.py             # FwImageInfo, FwPartSummary
|
|-- cli/                        # Click command-line interface
|   |-- main.py                 # Root group (--debug, --json-output, --version), serve
|   |-- device.py               # list, info, temp, status
|   +-- diag.py                 # eye, ltssm, loopback, patgen, patmon, inject, rcvr, eq
|
|-- api/                        # FastAPI REST + WebSocket API
|   |-- app.py                  # Application factory, CORS, lifespan, auth
|   |-- state.py                # Device registry, asyncio.Lock, API key auth
|   |-- error_handlers.py       # Exception-to-HTTP status mapping
|   +-- routes/                 # Route modules
|       |-- devices.py          # Device management endpoints
|       |-- ports.py            # Port status endpoints
|       +-- diagnostics.py      # Diagnostics endpoints
|
|-- ui/                         # NiceGUI browser dashboard
|   |-- main.py                 # Page registration, static file serving
|   |-- theme.py                # Dark theme, Serial Cables branding
|   |-- layout.py               # Shared page scaffold with logo header
|   |-- static/                 # Static assets
|   |   +-- logo.png            # Serial Cables logo (white, transparent)
|   |-- components/             # Reusable UI components
|   |   |-- device_card.py
|   |   |-- port_grid.py
|   |   |-- eye_chart.py
|   |   +-- ltssm_timeline.py
|   +-- pages/                  # Full-page views
|       |-- discovery.py
|       |-- dashboard.py
|       |-- ports.py
|       |-- eye_diagram.py
|       |-- ltssm_trace.py
|       +-- performance.py
|
+-- utils/
    +-- logging.py              # structlog configuration
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SWITCHTEC_LIB_DIR` | No | -- | Path to directory containing `libswitchtec.so` or `switchtec.dll` |
| `SWITCHTEC_API_KEY` | No | -- | API key for REST API authentication. If unset, authentication is disabled. |

### Server Options

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address. Use `0.0.0.0` for network access. |
| `--port` | `8000` | TCP port for the API server and dashboard. |

---

## Testing

The test suite uses pytest with pytest-asyncio for async test support and pytest-cov for coverage reporting.

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the full test suite
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=serialcables_switchtec --cov-report=term-missing
```

**Current status:** 91 tests (unit, integration, and end-to-end). Coverage is at 49%, primarily because the UI layer requires a NiceGUI runtime to test.

---

## Development Status

This project is under active development. The current version is **0.1.0**.

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Foundation -- bindings, core device, models, exceptions | Complete |
| Phase 2 | Diagnostics -- eye, LTSSM, loopback, pattern, EQ, injection, OSA | Complete |
| Phase 3 | CLI -- Click commands, JSON output, human-readable formatting | Complete |
| Phase 4 | REST API -- FastAPI endpoints, auth, WebSocket, error handling | Complete |
| Phase 5 | Browser UI -- NiceGUI dashboard, charts, dark theme | Complete |
| Phase 6 | Extended -- performance counters, firmware management, events, fabric | Planned |

---

## License

This project is licensed under the [MIT License](LICENSE).

The underlying `switchtec-user` C library is maintained by Microchip Technology Inc. and is subject to its own license terms. See the [switchtec-user repository](https://github.com/Microsemi/switchtec-user) for details.
