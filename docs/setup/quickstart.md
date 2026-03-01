# Quickstart Guide

Get Athena running with a Switchtec device in under 5 minutes.

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- A Switchtec device accessible at `/dev/switchtec0` (Linux) or `\\.\switchtec0` (Windows)
- The `libswitchtec` shared library (built from source or pre-packaged)

### Platform-Specific Requirements

| Platform | Requirements |
|----------|-------------|
| Linux    | `libswitchtec.so`, udev rule for device permissions |
| Windows  | MSYS2 build environment or pre-built `switchtec.dll` |

## 1. Install Athena

```bash
# Full install (CLI + API + Dashboard + dev tools)
pip install ".[all]"

# Or install specific components
pip install ".[api]"    # CLI + REST API
pip install ".[ui]"     # CLI + Browser Dashboard
pip install ".[dev]"    # Development tools (pytest, httpx, etc.)
```

## 2. Build the C Library

### Option A: Build Script (Recommended)

```bash
python scripts/build_lib.py
```

This clones `switchtec-user` into `vendor/switchtec/` and builds the shared library.

### Option B: Manual Build (Linux)

```bash
git clone https://github.com/Microsemi/switchtec-user vendor/switchtec
cd vendor/switchtec
./configure --prefix=$(pwd)
make && make install
cd ../..
```

### Option C: Windows (MSYS2)

```powershell
# Run the setup script
powershell -ExecutionPolicy Bypass -File scripts/setup_msys2.ps1
```

Or manually build in MSYS2:
```bash
cd vendor/switchtec
./configure && make
cp lib/.libs/libswitchtec*.dll ../..
```

## 3. Verify Library Loading

```bash
python -c "from serialcables_switchtec.bindings.library import load_library; load_library(); print('Library loaded successfully')"
```

If this fails, set `SWITCHTEC_LIB_DIR` to point to the directory containing the library:

```bash
export SWITCHTEC_LIB_DIR=/path/to/lib    # Linux
set SWITCHTEC_LIB_DIR=C:\path\to\lib     # Windows
```

## 4. Discover Devices

```bash
athena device list
```

Expected output:
```
PSX48XG5 [Gen5]  0000:03:00.0  FW 4.70B058  /dev/switchtec0
```

## 5. Start the Server

```bash
# Default: localhost:8000
athena serve

# Custom host/port
athena serve --host 0.0.0.0 --port 9000
```

## 6. Open the Dashboard

Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

1. The **Discovery** page opens by default
2. Click **Scan Devices** to find connected switches
3. Click **Connect** on a discovered device
4. The **Dashboard** shows device overview, temperature, and port status

## 7. Use the REST API

```bash
# List open devices
curl http://localhost:8000/api/devices/

# Open a device
curl -X POST http://localhost:8000/api/devices/sw0/open \
  -H "Content-Type: application/json" \
  -d '{"path": "/dev/switchtec0"}'

# Get device info
curl http://localhost:8000/api/devices/sw0

# Interactive API docs
open http://localhost:8000/docs
```

## Next Steps

- [Configuration Guide](configuration.md) -- environment variables, library paths, platform setup
- [API Reference](../api/reference.md) -- full endpoint documentation
- Run `athena --help` for all CLI commands
