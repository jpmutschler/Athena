# Configuration Guide

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SWITCHTEC_LIB_DIR` | No | (auto-detect) | Directory containing `libswitchtec.so` or `switchtec.dll` |
| `SWITCHTEC_API_KEY` | No | (disabled) | API key for X-API-Key header authentication |
| `ATHENA_LOG_LEVEL` | No | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |

See [`.env.example`](../../.env.example) for a template.

## Library Search Order

The Switchtec shared library is located automatically in this order:

| Priority | Location | Use Case |
|----------|----------|----------|
| 1 | `$SWITCHTEC_LIB_DIR/` | Explicit override |
| 2 | `<package>/_native/` | Pre-built wheel installs |
| 3 | `vendor/switchtec/lib/` | Dev/editable installs (`pip install -e .`) |
| 4 | `/usr/local/lib`, `/usr/lib`, `/usr/lib64`, `/opt/switchtec/lib` | System library paths (Linux only) |
| 5 | System `PATH` / `LD_LIBRARY_PATH` | Fallback by library name |

### Overriding the Search

```bash
# Linux
export SWITCHTEC_LIB_DIR=/opt/switchtec/lib

# Windows
set SWITCHTEC_LIB_DIR=C:\switchtec\lib
```

## API Server Options

Server configuration is set via CLI flags:

```bash
athena serve [OPTIONS]

Options:
  --host TEXT     Bind address (default: 127.0.0.1)
  --port INTEGER  Bind port (default: 8000)
```

### CORS

CORS origins are restricted to localhost by default:
- `http://localhost:8000`
- `http://127.0.0.1:8000`

### Rate Limiting

Destructive operations are rate-limited per device:

| Operation | Limit |
|-----------|-------|
| Hard reset | 1 per 60s |
| Error injection | 10 per 60s |
| Fabric control | 5 per 60s |
| Raw MRPC | 10 per 60s |
| CSR write | 5 per 60s |

### Authentication

When `SWITCHTEC_API_KEY` is set, all API requests (except `/api/health`) require the header:

```
X-API-Key: <your-key>
```

Authentication uses HMAC-SHA256 constant-time comparison. The health endpoint is always accessible without authentication.

## Windows Setup

### Prerequisites

1. Install [MSYS2](https://www.msys2.org/)
2. Install build tools: `pacman -S mingw-w64-x86_64-gcc make autoconf automake libtool`

### Build Steps

```powershell
# Automated setup
powershell -ExecutionPolicy Bypass -File scripts/setup_msys2.ps1

# Verify DLL
python -c "from serialcables_switchtec.bindings.library import load_library; load_library()"
```

### DLL Placement

Place `switchtec.dll` in one of:
- `SWITCHTEC_LIB_DIR` directory
- `src/serialcables_switchtec/_native/`
- `vendor/switchtec/lib/`
- A directory on your `PATH`

## Linux Setup

### Device Permissions

Switchtec devices require appropriate permissions. Create a udev rule:

```bash
# /etc/udev/rules.d/99-switchtec.rules
SUBSYSTEM=="switchtec", MODE="0666"
```

Reload rules:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Alternatively, add your user to the appropriate group:
```bash
sudo usermod -aG switchtec $USER
```

### System Library Installation

If installing system-wide:
```bash
cd vendor/switchtec
sudo make install
sudo ldconfig
```

## Troubleshooting

### Library Not Found

**Symptom:** `LibraryLoadError: Switchtec library not found`

**Solutions:**
1. Set `SWITCHTEC_LIB_DIR` to the directory containing the library
2. Run `python scripts/build_lib.py` to build from source
3. Check the error message for the list of searched paths
4. On Linux, run `ldconfig -p | grep switchtec` to verify system installation

### Permission Denied

**Symptom:** `SwitchtecPermissionError` when opening a device

**Solutions:**
1. Check device permissions: `ls -la /dev/switchtec*`
2. Add the udev rule above
3. Run with `sudo` (not recommended for production)

### Port Conflicts

**Symptom:** `Address already in use` when starting the server

**Solutions:**
1. Use a different port: `athena serve --port 9000`
2. Find and stop the conflicting process: `lsof -i :8000` (Linux) or `netstat -ano | findstr 8000` (Windows)

### Authentication Failures

**Symptom:** `403 Forbidden` on API requests

**Solutions:**
1. Verify `SWITCHTEC_API_KEY` matches your request header
2. Ensure the header name is `X-API-Key` (case-sensitive)
3. Unset `SWITCHTEC_API_KEY` to disable authentication for development
