# Athena -- serialcables-switchtec

<!-- Badges -->
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Build](https://img.shields.io/badge/build-hatchling-green.svg)](https://hatch.pypa.io/)
<!-- [![PyPI version](https://img.shields.io/pypi/v/serialcables-athena.svg)](https://pypi.org/project/serialcables-athena/) -->
<!-- [![CI](https://github.com/serialcables/serialcables-switchtec/actions/workflows/ci.yml/badge.svg)](https://github.com/serialcables/serialcables-switchtec/actions) -->
<!-- [![Coverage](https://img.shields.io/codecov/c/github/serialcables/serialcables-switchtec.svg)](https://codecov.io/gh/serialcables/serialcables-switchtec) -->

**Athena** is a Python-friendly interface to the Serial Cables Gen6 PCIe Switchtec Host Card (`switchtec-user` 4.4-rc2, 200+ API functions). Built for **PCIe Validation Engineers** who perform eye diagrams, LTSSM analysis, loopback testing, pattern generation and monitoring, error injection, receiver characterization, firmware management, and performance monitoring.

Developed by [Serial Cables](https://www.serialcables.com/), a manufacturer of PCIe test equipment and interposer solutions.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Building the C Library](#building-the-c-library)
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

**Click CLI** (`athena`) -- Full-featured command-line interface with human-readable output, `--json-output` mode for scripting, and `--debug` logging. Covers device discovery, port status, diagnostics, error injection, firmware management, events, fabric topology, and performance monitoring.

**FastAPI REST API** -- HTTP API with auto-generated OpenAPI documentation, API key authentication, input validation via Pydantic, rate limiting on destructive endpoints, WebSocket support for streaming diagnostics, and restricted CORS.

**NiceGUI Browser Dashboard** -- Dark-themed browser UI with Serial Cables branding. Provides real-time device cards, port grids, eye diagram charts, LTSSM timeline visualization, and performance monitoring.

**Diagnostics Suite** -- Comprehensive PCIe validation tooling:

| Capability | Description |
|---|---|
| Eye Diagrams | BER eye capture with configurable step size, lane selection, fetch, and cancel |
| LTSSM Analysis | State machine log capture, decode, and clear (Gen3/4/5/6 tables) |
| Loopback Testing | RX-to-TX, TX-to-RX, LTSSM, and PIPE loopback modes |
| Pattern Gen/Mon | PRBS7/9/11/15/23/31 pattern generation and bit-error monitoring |
| Error Injection | DLLP, DLLP CRC, TLP LCRC, sequence number, ACK/NACK, completion timeout |
| Receiver Characterization | CTLE, target amplitude, speculative DFE, dynamic DFE readout |
| Port Equalization | TX coefficient dump (local/far-end, current/previous link) |
| Cross-Hair Analysis | Per-lane eye limit measurement with enable/disable/get control |
| Ordered Set Analysis | Type/pattern configuration and capture control |

**Firmware Management** -- Read firmware data, write firmware images with progress callbacks, toggle active partitions, query/set boot read-only status, and view partition summaries.

**Events** -- Query event summary counts, clear all events, and wait for events with configurable timeouts.

**Fabric Topology** (PAX devices) -- Port enable/disable/hot-reset, port configuration, GFMS bind/unbind, and event clearing.

**Performance Monitoring** -- Bandwidth counters per port (egress/ingress posted, completion, non-posted) and latency measurement between port pairs.

**Security** -- API key authentication via `SWITCHTEC_API_KEY` environment variable with constant-time comparison (`hmac.compare_digest`), localhost-only binding by default, restricted CORS origins, Pydantic input validation on all API endpoints, firmware upload size limits (64 MB), port/lane ID range validation, rate limiting on destructive endpoints (hard reset, error injection, fabric control), sanitized error messages that never leak internal details, and thread-safe device access with per-device operation locks.

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
- **REST API** -- Thread-safe HTTP endpoints with a device registry protected by `threading.Lock`, input validation, rate limiting on destructive operations, sanitized error responses, and shared dependencies centralized in `api/dependencies.py`. Blocking C library calls run in FastAPI's thread pool; long-running operations (firmware write, event wait) use dedicated executors.
- **Core Domain** -- Business logic classes (`SwitchtecDevice`, `DiagnosticsManager`, `ErrorInjector`, `FirmwareManager`, `EventManager`, `FabricManager`, `PerformanceManager`, `OrderedSetAnalyzer`, `EventCounterManager`) that wrap C library calls and return immutable Pydantic models. Managers are accessible as thread-safe lazy properties on the device (e.g., `dev.diagnostics`, `dev.firmware`, `dev.performance`) with double-checked locking.
- **Bindings** -- Platform-aware CDLL loader, ctypes `Structure` definitions matching C structs (`_pack_ = 1` for MRPC structs), function prototypes with `argtypes`/`restype`, and IntEnum constants from C headers.

---

## Prerequisites

### Python

Python 3.10 or later is required.

### Switchtec C Library

Pre-built platform wheels for **Windows x86_64** and **Linux x86_64** include the native library — no separate compilation needed. Just `pip install serialcables-athena`.

For other platforms or custom builds, the library loader searches the following locations in order:

1. `SWITCHTEC_LIB_DIR` environment variable (explicit override)
2. `_native/` directory inside the installed package (pre-built wheel installs)
3. `vendor/switchtec/lib/` relative to the project root (dev environment, built by `scripts/build_lib.py`)
4. System library paths (`/usr/local/lib`, `/usr/lib`, `/usr/lib64`, `/opt/switchtec/lib`)
5. System `LD_LIBRARY_PATH` / `PATH` fallback

See [Building the C Library](#building-the-c-library) for manual build instructions.

**Using a custom path:**

```bash
export SWITCHTEC_LIB_DIR=/path/to/your/built/lib
```

### Hardware

A Microsemi/Microchip Switchtec PCIe switch device must be accessible at a device path such as `/dev/switchtec0` (Linux) or `\\.\switchtec0` (Windows). Appropriate permissions or elevated access may be required.

---

## Building the C Library

Pre-built wheels are available for Windows x86_64 and Linux x86_64. If you installed via `pip install serialcables-athena`, the native library is already included and this section can be skipped.

### Building from Source

The C source is included at [`switchtec-user-4.4-rc2/`](https://github.com/Microsemi/switchtec-user/releases/tag/v4.4-rc2). A cross-platform build script is provided.

```bash
python scripts/build_lib.py
```

This will compile the library and place it at `vendor/switchtec/lib/switchtec.dll` (Windows) or `vendor/switchtec/lib/libswitchtec.so` (Linux).

### Windows (MSYS2/MinGW)

The C code uses GCC-specific extensions (`__builtin_bswap*`, inline asm, `__builtin_ffs`) that are not compatible with MSVC. MSYS2/MinGW is required.

1. **Install MSYS2** (if not already installed):

   ```powershell
   .\scripts\setup_msys2.ps1
   ```

   This downloads and installs MSYS2 to `C:\msys64` with the MinGW64 toolchain (`gcc`, `make`, `autotools`).

2. **Build the library:**

   ```bash
   python scripts/build_lib.py
   ```

   The script locates MSYS2, runs `./configure && make` inside the MinGW shell, and copies the output to `vendor/switchtec/lib/switchtec.dll`.

### Linux

GCC and standard build tools (`make`, `autoconf`, `automake`, `libtool`) must be installed.

```bash
# Install build dependencies (Debian/Ubuntu)
sudo apt install build-essential autoconf automake libtool

# Build
python scripts/build_lib.py
```

### Manual Build

```bash
cd resources/switchtec-user-4.4-rc2
./configure
make

# Copy library to vendor location
cp lib/.libs/libswitchtec.so ../../vendor/switchtec/lib/       # Linux
cp lib/.libs/switchtec-0.dll ../../vendor/switchtec/lib/switchtec.dll  # Windows/MinGW
```

### Verification

```bash
python -c "from serialcables_switchtec.bindings.library import load_library; load_library(); print('OK')"
```

---

## Installation

**Core only** (CLI + Python library, no server dependencies):

```bash
pip install serialcables-athena
```

**With REST API** (adds FastAPI, Uvicorn, WebSockets):

```bash
pip install "serialcables-athena[api]"
```

**With browser dashboard** (adds NiceGUI):

```bash
pip install "serialcables-athena[ui]"
```

**Everything** (API + UI):

```bash
pip install "serialcables-athena[all]"
```

**Development** (adds pytest, ruff, httpx, pytest-asyncio, pytest-cov):

```bash
pip install "serialcables-athena[dev]"
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
pip install "serialcables-athena[all]"
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

# Hard-reset the switch (requires confirmation)
athena device hard-reset /dev/switchtec0
athena device hard-reset /dev/switchtec0 --yes  # Skip confirmation
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
# Start eye diagram capture
athena diag eye /dev/switchtec0 --lanes 1,0,0,0 --x-step 1 --y-step 2

# Fetch eye diagram data from an in-progress capture
athena diag eye-fetch /dev/switchtec0 --pixels 4096

# Cancel eye diagram capture
athena diag eye-cancel /dev/switchtec0
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

All error injection commands are under `athena diag inject`. Port IDs are validated to the range 0-59.

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

### Firmware Commands

```bash
# Show firmware version
athena fw version /dev/switchtec0

# Show firmware partition summary
athena fw summary /dev/switchtec0

# Read raw firmware data at address
athena fw read /dev/switchtec0 --address 0x1000 --length 256

# Write a firmware image (with progress display)
athena fw write /dev/switchtec0 firmware.bin

# Write without activating
athena fw write /dev/switchtec0 firmware.bin --no-activate

# Toggle active firmware partition
athena fw toggle /dev/switchtec0 --fw --cfg

# Show/set boot partition read-only status
athena fw boot-ro /dev/switchtec0
athena fw boot-ro /dev/switchtec0 --set
athena fw boot-ro /dev/switchtec0 --clear
```

### Event Commands

```bash
# Show event summary counts
athena events summary /dev/switchtec0

# Clear all events
athena events clear /dev/switchtec0

# Wait for an event (with optional timeout)
athena events wait /dev/switchtec0 --timeout 5000
```

### Fabric Commands (PAX Devices)

```bash
# Enable/disable/hot-reset a fabric port
athena fabric port-control /dev/switchtec0 --port 4 --action enable
athena fabric port-control /dev/switchtec0 --port 4 --action hot-reset --hot-reset-flag perst

# Get fabric port configuration
athena fabric port-config /dev/switchtec0 --port 4

# Bind a host port to an endpoint port
athena fabric bind /dev/switchtec0 \
    --host-sw-idx 0 --host-phys-port 0 --host-log-port 0 \
    --ep-sw-idx 0 --ep-phys-port 4

# Unbind
athena fabric unbind /dev/switchtec0 \
    --host-sw-idx 0 --host-phys-port 0 --host-log-port 0

# Clear GFMS events
athena fabric clear-events /dev/switchtec0
```

### Performance Commands

```bash
# Get bandwidth counters for ports 0, 1, and 4
athena perf bw /dev/switchtec0 --ports 0,1,4

# Configure latency measurement between egress port 0 and ingress port 4
athena perf latency-setup /dev/switchtec0 --egress 0 --ingress 4

# Read latency measurement
athena perf latency /dev/switchtec0 --egress 0
```

### Ordered Set Analyzer (OSA) Commands

```bash
# Start/stop OSA capture on a stack
athena osa start /dev/switchtec0 --stack 0
athena osa stop /dev/switchtec0 --stack 0

# Configure type filter
athena osa config-type /dev/switchtec0 --stack 0 --direction 0 \
    --lane-mask 0xff --link-rate 4 --os-types 0x1

# Configure pattern match filter
athena osa config-pattern /dev/switchtec0 --stack 0 --direction 0 \
    --lane-mask 0xff --link-rate 4 \
    --value 0x1,0x2,0x3,0x4 --mask 0xff,0xff,0xff,0xff

# Configure and start capture control
athena osa capture /dev/switchtec0 --stack 0 --lane-mask 0xff --direction 0

# Read captured data
athena osa read /dev/switchtec0 --stack 0 --lane 0 --direction 0

# Dump current OSA configuration
athena osa dump-config /dev/switchtec0 --stack 0
```

### Event Counter Commands

Event counters are critical for BER (Bit Error Rate) testing and continuous error monitoring.

```bash
# Configure event counter 0 on stack 0 to count all errors on port 0
athena evcntr setup /dev/switchtec0 --stack 0 --counter 0 \
    --port-mask 0x1 --type-mask 0x7ffff

# Read counter values
athena evcntr read /dev/switchtec0 --stack 0 --counter 0 --count 4

# Read with setup info and clear after reading
athena evcntr read /dev/switchtec0 --stack 0 --counter 0 --show-setup --clear

# Show counter setup configuration
athena evcntr get-setup /dev/switchtec0 --stack 0 --counter 0 --count 4
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

Set the `SWITCHTEC_API_KEY` environment variable before starting the server. All API requests must include the key in the `X-API-Key` header. The key is verified using `hmac.compare_digest` to prevent timing attacks.

```bash
export SWITCHTEC_API_KEY="your-secret-key"
athena serve
```

```bash
curl -H "X-API-Key: your-secret-key" http://127.0.0.1:8000/api/devices/
```

### Endpoints

**Device Management:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (no auth required) |
| `GET` | `/api/devices/` | List managed device sessions |
| `GET` | `/api/devices/discover` | Discover available Switchtec devices |
| `POST` | `/api/devices/{id}/open` | Open a device by path |
| `DELETE` | `/api/devices/{id}` | Close a device session |
| `GET` | `/api/devices/{id}` | Get device summary info |
| `GET` | `/api/devices/{id}/temperature` | Read die temperature |
| `POST` | `/api/devices/{id}/hard-reset` | Hard-reset device (requires `confirm: true` body) |
| `GET` | `/api/devices/{id}/ports` | List port status |
| `GET` | `/api/devices/{id}/ports/{port}/pff` | Get PFF index for a port |

**Diagnostics:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/devices/{id}/diag/eye/start` | Start eye diagram capture |
| `GET` | `/api/devices/{id}/diag/eye/fetch` | Fetch eye diagram data |
| `POST` | `/api/devices/{id}/diag/eye/cancel` | Cancel eye diagram capture |
| `GET` | `/api/devices/{id}/diag/ltssm/{port}` | Get LTSSM state log |
| `DELETE` | `/api/devices/{id}/diag/ltssm/{port}` | Clear LTSSM log |
| `GET` | `/api/devices/{id}/diag/loopback/{port}` | Get loopback status |
| `POST` | `/api/devices/{id}/diag/loopback/{port}` | Set loopback mode |
| `POST` | `/api/devices/{id}/diag/patgen/{port}` | Set pattern generator |
| `GET` | `/api/devices/{id}/diag/patmon/{port}/{lane}` | Get pattern monitor results |
| `POST` | `/api/devices/{id}/diag/inject/dllp/{port}` | Inject DLLP |
| `POST` | `/api/devices/{id}/diag/inject/dllp-crc/{port}` | DLLP CRC error injection |
| `POST` | `/api/devices/{id}/diag/inject/tlp-lcrc/{port}` | TLP LCRC error injection |
| `POST` | `/api/devices/{id}/diag/inject/seq-num/{port}` | Sequence number error injection |
| `POST` | `/api/devices/{id}/diag/inject/ack-nack/{port}` | ACK/NACK error injection |
| `POST` | `/api/devices/{id}/diag/inject/cto/{port}` | Inject completion timeout |
| `GET` | `/api/devices/{id}/diag/rcvr/{port}/{lane}` | Dump receiver object |
| `GET` | `/api/devices/{id}/diag/eq/{port}` | Get port EQ TX coefficients |
| `POST` | `/api/devices/{id}/diag/crosshair/enable/{lane}` | Enable cross-hair |
| `POST` | `/api/devices/{id}/diag/crosshair/disable` | Disable cross-hair |
| `GET` | `/api/devices/{id}/diag/crosshair` | Get cross-hair results |

**Firmware:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/devices/{id}/firmware/version` | Get firmware version |
| `GET` | `/api/devices/{id}/firmware/summary` | Get partition summary |
| `GET` | `/api/devices/{id}/firmware/boot-ro` | Check boot RO status |
| `POST` | `/api/devices/{id}/firmware/boot-ro` | Set boot RO flag |
| `POST` | `/api/devices/{id}/firmware/toggle` | Toggle active partition |
| `POST` | `/api/devices/{id}/firmware/write` | Write firmware (multipart, 64 MB limit) |

**Events:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/devices/{id}/events/summary` | Get event summary |
| `POST` | `/api/devices/{id}/events/clear` | Clear all events |
| `POST` | `/api/devices/{id}/events/wait` | Wait for event |

**Fabric:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/devices/{id}/fabric/port-control` | Enable/disable/hot-reset port |
| `GET` | `/api/devices/{id}/fabric/port-config/{port}` | Get port configuration |
| `POST` | `/api/devices/{id}/fabric/port-config/{port}` | Set port configuration |
| `POST` | `/api/devices/{id}/fabric/bind` | GFMS bind |
| `POST` | `/api/devices/{id}/fabric/unbind` | GFMS unbind |
| `POST` | `/api/devices/{id}/fabric/clear-events` | Clear GFMS events |

**Performance:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/devices/{id}/perf/bw` | Get bandwidth counters |
| `POST` | `/api/devices/{id}/perf/latency/setup` | Configure latency measurement |
| `GET` | `/api/devices/{id}/perf/latency/{port}` | Get latency measurement |

**Ordered Set Analyzer (OSA):**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/devices/{id}/osa/{stack}/start` | Start OSA capture |
| `POST` | `/api/devices/{id}/osa/{stack}/stop` | Stop OSA capture |
| `POST` | `/api/devices/{id}/osa/{stack}/config-type` | Configure type filter |
| `POST` | `/api/devices/{id}/osa/{stack}/config-pattern` | Configure pattern filter |
| `POST` | `/api/devices/{id}/osa/{stack}/capture` | Configure capture control |
| `GET` | `/api/devices/{id}/osa/{stack}/data/{lane}` | Read captured data |
| `GET` | `/api/devices/{id}/osa/{stack}/dump-config` | Dump OSA configuration |

**Event Counters:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/devices/{id}/evcntr/{stack}/{counter}/setup` | Configure event counter |
| `GET` | `/api/devices/{id}/evcntr/{stack}/{counter}/setup` | Get counter setup |
| `GET` | `/api/devices/{id}/evcntr/{stack}/{counter}/counts` | Read counter values |
| `GET` | `/api/devices/{id}/evcntr/{stack}/{counter}` | Get setup + values |

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
from serialcables_switchtec.bindings.constants import (
    DiagPattern,
    DiagPatternLinkRate,
    DiagLink,
)

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    diag = dev.diagnostics  # Lazy-initialized DiagnosticsManager

    # Start an eye diagram capture
    diag.eye_start(lane_mask=[1, 0, 0, 0], x_step=1, y_step=2)

    # Fetch eye diagram data
    eye_data = diag.eye_fetch(pixel_count=4096)
    print(f"Lane {eye_data.lane_id}: {len(eye_data.pixels)} pixels")

    # Cancel capture
    diag.eye_cancel()

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

### Firmware Management

```python
from serialcables_switchtec.core.device import SwitchtecDevice

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    fw = dev.firmware  # Lazy-initialized FirmwareManager

    # Get firmware version
    print(f"FW Version: {fw.get_fw_version()}")

    # Check boot read-only status
    print(f"Boot RO: {fw.is_boot_ro()}")

    # Get partition summary
    summary = fw.get_part_summary()

    # Write firmware image with progress callback
    def progress(cur: int, tot: int) -> None:
        print(f"\rProgress: {cur * 100 // tot}%", end="")

    fw.write_firmware("firmware.bin", progress_callback=progress)
    print("\nDone")

    # Toggle active partition
    fw.toggle_active_partition(toggle_fw=True, toggle_cfg=True)
```

### Events

```python
from serialcables_switchtec.core.device import SwitchtecDevice

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    events = dev.events  # Lazy-initialized EventManager

    # Get event summary
    summary = events.get_summary()
    print(f"Total events: {summary.total_count}")

    # Clear all events
    events.clear_all()

    # Wait for an event (5 second timeout)
    events.wait_for_event(timeout_ms=5000)
```

### Fabric Topology (PAX Devices)

```python
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.models.fabric import GfmsBindRequest

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    fab = dev.fabric  # Lazy-initialized FabricManager

    # Get port configuration
    config = fab.get_port_config(port_id=4)
    print(f"Port type: {config.port_type}")

    # Bind host to endpoint
    req = GfmsBindRequest(
        host_sw_idx=0,
        host_phys_port_id=0,
        host_log_port_id=0,
        ep_sw_idx=0,
        ep_phys_port_id=4,
    )
    fab.bind(req)
```

### Performance Monitoring

```python
from serialcables_switchtec.core.device import SwitchtecDevice

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    perf = dev.performance  # Lazy-initialized PerformanceManager

    # Get bandwidth counters for ports 0 and 4
    results = perf.bw_get([0, 4])
    for r in results:
        print(f"Egress total: {r.egress.total}  Ingress total: {r.ingress.total}")

    # Configure and read latency
    perf.lat_setup(egress_port_id=0, ingress_port_id=4)
    lat = perf.lat_get(egress_port_id=0)
    print(f"Latency: current={lat.current_ns} ns  max={lat.max_ns} ns")
```

### Ordered Set Analyzer

```python
from serialcables_switchtec.core.device import SwitchtecDevice

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    osa = dev.osa  # Lazy-initialized OrderedSetAnalyzer

    # Configure and start capture
    osa.configure_type(stack_id=0, direction=0, lane_mask=0xFF, link_rate=4, os_types=0x1)
    osa.start(stack_id=0)

    # Read captured data
    result = osa.capture_data(stack_id=0, lane=0, direction=0)

    # Stop capture
    osa.stop(stack_id=0)
```

### Event Counters

```python
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.bindings.constants import EvCntrTypeMask

with SwitchtecDevice.open("/dev/switchtec0") as dev:
    evcntr = dev.evcntr  # Lazy-initialized EventCounterManager

    # Configure counter 0 on stack 0 to count all errors on port 0
    evcntr.setup(stack_id=0, counter_id=0, port_mask=0x1,
                 type_mask=EvCntrTypeMask.ALL_ERRORS)

    # Read counter values
    counts = evcntr.get_counts(stack_id=0, counter_id=0, nr_counters=4)
    for i, c in enumerate(counts):
        print(f"Counter {i}: {c}")

    # Read setup and values together
    values = evcntr.get_both(stack_id=0, counter_id=0, nr_counters=4)
    for v in values:
        print(f"Counter {v.counter_id}: {v.count} ({v.setup})")
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
scripts/
|-- setup_msys2.ps1            # MSYS2/MinGW installer for Windows
+-- build_lib.py               # Cross-platform C library build script

vendor/switchtec/lib/          # Built shared library output directory

resources/switchtec-user-4.4-rc2/  # C library source

src/serialcables_switchtec/
|-- _native/                    # Pre-built native libraries (populated in wheels)
|   +-- __init__.py
|-- __init__.py                 # Package entry point, exports SwitchtecError
|-- exceptions.py               # Exception hierarchy with errno/MRPC mapping
|
|-- bindings/                   # ctypes interface to libswitchtec
|   |-- library.py              # Platform-aware CDLL loader (env, _native, vendor, system)
|   |-- constants.py            # IntEnums from C headers (Gen, Variant, LTSSM, patterns)
|   |-- types.py                # ctypes Structure definitions matching C structs
|   +-- functions.py            # Function prototypes (argtypes/restype)
|
|-- core/                       # Business logic wrapping C library calls
|   |-- device.py               # SwitchtecDevice: open/close/list/status/temp + lazy managers
|   |-- diagnostics.py          # DiagnosticsManager: eye, LTSSM, loopback, pattern, EQ
|   |-- error_injection.py      # ErrorInjector: DLLP, TLP LCRC, seq num, ACK/NACK, CTO
|   |-- evcntr.py               # EventCounterManager: setup, read, wait
|   |-- firmware.py             # FirmwareManager: version, read, write, toggle, boot-ro
|   |-- events.py               # EventManager: summary, clear, wait
|   |-- fabric.py               # FabricManager: port control/config, bind/unbind, events
|   |-- osa.py                  # OrderedSetAnalyzer: type/pattern config, capture control
|   +-- performance.py          # PerformanceManager: bandwidth counters, latency
|
|-- models/                     # Pydantic models (frozen, immutable)
|   |-- device.py               # DeviceInfo, PortId, PortStatus, DeviceSummary
|   |-- diagnostics.py          # EyeData, LtssmLogEntry, CrossHairResult, ReceiverObject
|   |-- evcntr.py               # EvCntrSetupResult, EvCntrValue, EvCntrSetupRequest
|   |-- performance.py          # BwCounterResult, LatencyResult, EventCounterResult
|   |-- firmware.py             # FwImageInfo, FwPartSummary
|   |-- events.py               # EventSummaryResult
|   +-- fabric.py               # FabPortConfig, GfmsBindRequest, GfmsUnbindRequest
|
|-- cli/                        # Click command-line interface
|   |-- main.py                 # Root group (--debug, --json-output, --version), serve
|   |-- device.py               # list, info, temp, status, hard-reset
|   |-- diag.py                 # eye, eye-fetch, eye-cancel, ltssm, loopback, patgen, patmon, inject, rcvr, eq, crosshair
|   |-- evcntr.py               # setup, read, get-setup
|   |-- firmware.py             # version, summary, read, write, toggle, boot-ro
|   |-- events.py               # summary, clear, wait
|   |-- fabric.py               # port-control, port-config, bind, unbind, clear-events
|   |-- osa.py                  # start, stop, config-type, config-pattern, capture, read, dump-config
|   +-- perf.py                 # bw, latency-setup, latency
|
|-- api/                        # FastAPI REST + WebSocket API
|   |-- app.py                  # Application factory, CORS, lifespan, auth
|   |-- state.py                # Device registry, threading.Lock, API key auth
|   |-- dependencies.py         # Shared helpers: get_device(), DEVICE_ID_PATTERN
|   |-- error_handlers.py       # Exception-to-HTTP status mapping with sanitized messages
|   |-- rate_limit.py           # Per-device rate limiting for destructive endpoints
|   +-- routes/                 # Route modules
|       |-- devices.py          # Device management + hard-reset endpoints
|       |-- ports.py            # Port status endpoints
|       |-- diagnostics.py      # Eye, LTSSM, loopback, pattern, injection, EQ, crosshair
|       |-- evcntr.py           # Event counter setup, read, get-both
|       |-- firmware.py         # Firmware version, write, toggle, boot-ro, summary
|       |-- events.py           # Event summary, clear, wait
|       |-- fabric.py           # Fabric port control/config, bind/unbind, events
|       |-- osa.py              # OSA start, stop, config, capture, data
|       +-- performance.py      # Bandwidth and latency endpoints
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

tests/
|-- unit/                       # Unit tests (mocked C library calls)
|-- integration/                # Integration tests
+-- e2e/                        # End-to-end CLI and API tests
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

**Current status:** 836 tests across unit, integration, and end-to-end suites organized by domain (device, diagnostics, firmware, events, fabric, performance, error handlers). Coverage is at 84%. The UI layer requires a NiceGUI runtime and is not covered by automated tests.

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
| Phase 6 | Extended -- firmware management, events, fabric, performance | Complete |
| Phase 7 | C Library Build System -- MSYS2/MinGW scripts, vendor directory | Complete |
| Phase 8 | P0 Feature Gaps -- eye fetch, firmware write, performance CLI/API | Complete |
| Phase 9 | Code Quality -- shared dependencies, input validation, dead code removal | Complete |

---

## License

This project is licensed under the [MIT License](LICENSE).

The underlying `switchtec-user` C library is maintained by Microchip Technology Inc. and is subject to its own license terms. See the [switchtec-user repository](https://github.com/Microsemi/switchtec-user) for details.
