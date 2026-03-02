# API Reference

Athena exposes a REST API for managing Switchtec devices programmatically. When the server is running, interactive Swagger UI is available at `/docs` and ReDoc at `/redoc`.

## Overview

| Property | Value |
|----------|-------|
| Base URL | `http://localhost:8000/api` |
| Content Type | `application/json` (except SSE endpoints) |
| Version | 0.1.0 |
| OpenAPI Spec | `GET /openapi.json` |

## Authentication

Authentication is **optional**. When the `SWITCHTEC_API_KEY` environment variable is set on the server, all endpoints (except `/api/health`) require the `X-API-Key` header.

```bash
# With authentication enabled
curl -H "X-API-Key: your-key" http://localhost:8000/api/devices/

# Without authentication (SWITCHTEC_API_KEY not set)
curl http://localhost:8000/api/devices/
```

Authentication uses HMAC-SHA256 constant-time comparison (`hmac.compare_digest`).

## Error Format

All errors return a JSON body with a `detail` field:

```json
{
  "detail": "Device not found"
}
```

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request completed |
| 400 | Bad Request | Invalid parameters (port out of range, bad format) |
| 403 | Forbidden | Missing or invalid API key |
| 404 | Not Found | Device not in registry |
| 409 | Conflict | Device already open |
| 422 | Unprocessable Entity | Request body validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 501 | Not Implemented | Feature not supported by device |
| 502 | Bad Gateway | Device communication error (MRPC, open failure) |
| 504 | Gateway Timeout | Device operation timed out |

## Rate Limiting

Destructive operations are rate-limited per device using a token-bucket algorithm:

| Operation | Limit | Endpoints |
|-----------|-------|-----------|
| Hard reset | 1 / 60s | `POST /{device_id}/hard-reset` |
| Error injection | 10 / 60s | `POST /{device_id}/diag/inject/*` |
| Fabric control | 5 / 60s | `POST /{device_id}/fabric/port-control`, bind, unbind |
| Raw MRPC | 10 / 60s | `POST /{device_id}/mrpc` |
| CSR write | 5 / 60s | `POST /{device_id}/fabric/csr/{pdfid}` |

---

## Endpoints by Group

### Health

```bash
# Health check (no auth required)
curl http://localhost:8000/api/health
# {"status": "ok"}
```

### Devices

```bash
# List open devices
curl http://localhost:8000/api/devices/

# Discover system devices
curl http://localhost:8000/api/devices/discover

# Open a device
curl -X POST http://localhost:8000/api/devices/sw0/open \
  -H "Content-Type: application/json" \
  -d '{"path": "/dev/switchtec0"}'

# Get device summary
curl http://localhost:8000/api/devices/sw0

# Get die temperature
curl http://localhost:8000/api/devices/sw0/temperature

# Close a device
curl -X DELETE http://localhost:8000/api/devices/sw0

# Hard reset (requires confirm)
curl -X POST http://localhost:8000/api/devices/sw0/hard-reset \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

### Ports

```bash
# List all port statuses
curl http://localhost:8000/api/devices/sw0/ports

# Get PFF mapping for a port
curl http://localhost:8000/api/devices/sw0/ports/0/pff
```

### Diagnostics -- Eye Diagram

```bash
# Start eye capture
curl -X POST http://localhost:8000/api/devices/sw0/diag/eye/start \
  -H "Content-Type: application/json" \
  -d '{"port_id": 0, "lane_id": 0, "x_step": 1, "y_step": 1}'

# Fetch eye data (poll until ready)
curl http://localhost:8000/api/devices/sw0/diag/eye/fetch

# Cancel capture
curl -X POST http://localhost:8000/api/devices/sw0/diag/eye/cancel
```

### Diagnostics -- LTSSM

```bash
# Get LTSSM log
curl http://localhost:8000/api/devices/sw0/diag/ltssm/0

# Clear LTSSM log
curl -X DELETE http://localhost:8000/api/devices/sw0/diag/ltssm/0
```

### Diagnostics -- Loopback

```bash
# Get loopback status
curl http://localhost:8000/api/devices/sw0/diag/loopback/0

# Set loopback (mode: 0=off, 1=RX-to-TX, 2=TX-to-RX, 3=LTSSM, 4=PIPE)
curl -X POST http://localhost:8000/api/devices/sw0/diag/loopback/0 \
  -H "Content-Type: application/json" \
  -d '{"loopback_mode": 1}'
```

### Diagnostics -- Pattern Gen/Mon

```bash
# Set pattern generator
curl -X POST http://localhost:8000/api/devices/sw0/diag/patgen/0 \
  -H "Content-Type: application/json" \
  -d '{"pattern_type": 1}'

# Get pattern monitor results
curl http://localhost:8000/api/devices/sw0/diag/patmon/0/0
```

### Diagnostics -- Error Injection

```bash
# Inject DLLP error
curl -X POST http://localhost:8000/api/devices/sw0/diag/inject/dllp/0 \
  -H "Content-Type: application/json" \
  -d '{"err_type": 1}'

# Generate AER event
curl -X POST http://localhost:8000/api/devices/sw0/diag/aer-gen/0 \
  -H "Content-Type: application/json" \
  -d '{"error_type": 1}'
```

### Diagnostics -- Receiver & Equalization

```bash
# Get receiver calibration
curl http://localhost:8000/api/devices/sw0/diag/rcvr/0/0

# Get equalization coefficients
curl http://localhost:8000/api/devices/sw0/diag/eq/0
```

### Diagnostics -- Cross-Hair Margin

```bash
# Enable cross-hair on lane 0
curl -X POST http://localhost:8000/api/devices/sw0/diag/crosshair/enable/0

# Get cross-hair results (poll until state=DONE)
curl http://localhost:8000/api/devices/sw0/diag/crosshair

# Disable cross-hair
curl -X POST http://localhost:8000/api/devices/sw0/diag/crosshair/disable
```

### Event Counters

```bash
# Setup a counter
curl -X POST http://localhost:8000/api/devices/sw0/evcntr/0/0/setup \
  -H "Content-Type: application/json" \
  -d '{"port_mask": 1, "type_mask": 65535, "egress": false, "threshold": 0}'

# Read counter setup
curl http://localhost:8000/api/devices/sw0/evcntr/0/0/setup

# Read counter values
curl http://localhost:8000/api/devices/sw0/evcntr/0/0
```

### Events

```bash
# Get event summary
curl http://localhost:8000/api/devices/sw0/events/summary

# Clear all events
curl -X POST http://localhost:8000/api/devices/sw0/events/clear

# Wait for event (blocks up to timeout seconds)
curl -X POST http://localhost:8000/api/devices/sw0/events/wait \
  -H "Content-Type: application/json" \
  -d '{"event_id": 0, "timeout": 30}'
```

### Firmware

```bash
# Get firmware version
curl http://localhost:8000/api/devices/sw0/firmware/version

# Get partition summary
curl http://localhost:8000/api/devices/sw0/firmware/summary

# Toggle active partition
curl -X POST http://localhost:8000/api/devices/sw0/firmware/toggle

# Get boot read-only status
curl http://localhost:8000/api/devices/sw0/firmware/boot-ro

# Upload firmware image (max 64 MB)
curl -X POST http://localhost:8000/api/devices/sw0/firmware/write \
  -F "file=@firmware.img"
```

### Fabric (PAX Devices)

```bash
# Port control (hot reset, enable, disable)
curl -X POST http://localhost:8000/api/devices/sw0/fabric/port-control \
  -H "Content-Type: application/json" \
  -d '{"phys_port_id": 0, "control_type": "enable"}'

# Bind host to endpoint
curl -X POST http://localhost:8000/api/devices/sw0/fabric/bind \
  -H "Content-Type: application/json" \
  -d '{"host_port": 0, "endpoint_port": 4}'

# Read config space register (standard 0-4KB range)
curl "http://localhost:8000/api/devices/sw0/fabric/csr/0?addr=0&width=32"

# Read extended config space register (0-64KB range via Switchtec MRPC)
curl "http://localhost:8000/api/devices/sw0/fabric/csr/0?addr=0x1000&width=32&extended=true"

# Write config space register (standard range)
curl -X POST http://localhost:8000/api/devices/sw0/fabric/csr/0 \
  -H "Content-Type: application/json" \
  -d '{"addr": 0, "value": 255, "width": 32}'

# Write extended config space register (0-64KB range)
curl -X POST http://localhost:8000/api/devices/sw0/fabric/csr/0 \
  -H "Content-Type: application/json" \
  -d '{"addr": 4096, "value": 255, "width": 32, "extended": true}'
```

**CSR `extended` parameter:** When `extended=true`, the address range expands from 0x000-0xFFF (standard 4KB) to 0x000-0xFFFF (64KB). Extended access uses Switchtec MRPC tunneled access rather than host ECAM. Default is `false` (backward compatible).

### Performance

```bash
# Read bandwidth counters
curl -X POST http://localhost:8000/api/devices/sw0/perf/bw \
  -H "Content-Type: application/json" \
  -d '{"port_ids": [0, 4], "clear": true}'

# Setup latency measurement
curl -X POST http://localhost:8000/api/devices/sw0/perf/latency/setup \
  -H "Content-Type: application/json" \
  -d '{"egress_port_id": 0, "ingress_port_id": 4, "clear": true}'

# Read latency
curl "http://localhost:8000/api/devices/sw0/perf/latency/0?clear=true"
```

### Raw MRPC

```bash
# Send raw MRPC command (hex-encoded payload)
curl -X POST http://localhost:8000/api/devices/sw0/mrpc \
  -H "Content-Type: application/json" \
  -d '{"command": 1, "payload": "00000000", "resp_len": 4}'
```

### Ordered Set Analyzer

```bash
# Start OSA capture
curl -X POST http://localhost:8000/api/devices/sw0/osa/0/start

# Stop capture
curl -X POST http://localhost:8000/api/devices/sw0/osa/0/stop

# Fetch captured data
curl http://localhost:8000/api/devices/sw0/osa/0/data/0
```

---

## Streaming Endpoints (SSE)

The monitor endpoints use **Server-Sent Events** (SSE) to stream data in real time. Each event is a JSON line prefixed with `data: `.

### Bandwidth Monitor

```bash
# Stream 10 bandwidth samples at 1-second intervals
curl -N "http://localhost:8000/api/devices/sw0/monitor/bw?port_ids=0,4&interval=1.0&count=10"
```

**Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `port_ids` | string | (required) | 0-59 | Comma-separated physical port IDs |
| `interval` | float | 1.0 | 0.1-60.0 | Seconds between samples |
| `count` | int | 60 | 0-86400 | Number of samples (0 = infinite) |

**Response format** (`text/event-stream`):
```
data: {"timestamp":1709312456.7,"elapsed_s":1.0,"iteration":1,"port_id":0,"time_us":1000234,"egress_total":1576960,"ingress_total":788480,...}

data: {"timestamp":1709312456.7,"elapsed_s":1.0,"iteration":1,"port_id":4,"time_us":1000234,"egress_total":524288,"ingress_total":262144,...}

```

### Event Counter Monitor

```bash
# Stream event counter samples
curl -N "http://localhost:8000/api/devices/sw0/monitor/evcntr?stack_id=0&counter_id=0&interval=1.0&count=60"
```

**Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `stack_id` | int | (required) | 0-7 | Stack ID |
| `counter_id` | int | (required) | 0+ | Starting counter ID |
| `nr_counters` | int | 1 | 1-64 | Number of consecutive counters |
| `interval` | float | 1.0 | 0.1-60.0 | Seconds between samples |
| `count` | int | 60 | 0-86400 | Number of samples (0 = infinite) |

**Response format** (`text/event-stream`):
```
data: {"timestamp":1709312456.7,"elapsed_s":1.0,"iteration":1,"stack_id":0,"counter_id":0,"count":42,"delta":42}

```

### JavaScript EventSource Example

```javascript
const source = new EventSource(
  '/api/devices/sw0/monitor/bw?port_ids=0,4&interval=1.0&count=0'
);

source.onmessage = (event) => {
  const sample = JSON.parse(event.data);
  console.log(`Port ${sample.port_id}: ${sample.egress_total} bytes egress`);
};

source.onerror = () => {
  source.close();
};
```

---

## Auto-Generated Documentation

When the server is running:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
