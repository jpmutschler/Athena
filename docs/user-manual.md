# Athena Switchtec Switch Manager -- User's Manual

**Version:** 1.0
**Date:** 2026-03-01
**Audience:** PCIe Validation Engineers

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [UI Overview](#2-ui-overview)
3. [Discovery Page](#3-discovery-page)
4. [Dashboard](#4-dashboard)
5. [Ports Page](#5-ports-page)
6. [Firmware Management](#6-firmware-management)
7. [Events Page](#7-events-page)
8. [Event Counters](#8-event-counters)
9. [Eye Diagram Capture](#9-eye-diagram-capture)
10. [LTSSM Trace](#10-ltssm-trace)
11. [Performance Monitoring](#11-performance-monitoring)
12. [Workflows](#12-workflows)
13. [Fabric / Topology Management](#13-fabric--topology-management)
14. [Error Injection](#14-error-injection)
15. [BER Testing](#15-ber-testing)
16. [Equalization & Margin](#16-equalization--margin)
17. [Ordered Set Analyzer](#17-ordered-set-analyzer)
18. [Common UI Patterns & Tips](#18-common-ui-patterns--tips)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Introduction

### What Is Athena

Athena is a Python-based management interface for the **Serial Cables Gen6 PCIe Switchtec Host Card**. It wraps the `switchtec-user` 4.4-rc2 C library (200+ API functions) and presents a real-time browser dashboard built with NiceGUI v2.0+. The dashboard communicates with the browser over WebSocket, providing reactive updates without page reloads. Charts and visualizations use Plotly.

Athena gives you a single pane of glass for every operational task on a Switchtec switch: device discovery, port inspection, firmware management, eye diagram capture, BER testing, equalization analysis, error injection, performance monitoring, and pre-composed validation workflows.

### Target Audience

This manual is written for **PCIe Validation Engineers** who need to:

- Manage and monitor Switchtec PCIe switches through a browser UI.
- Debug link training failures and LTSSM state transitions.
- Capture eye diagrams and measure signal integrity margins.
- Run BER soak tests and loopback sweeps.
- Inject PCIe errors and verify link recovery behavior.
- Profile bandwidth and latency across switch ports.
- Manage firmware partitions and fabric topology.
- Execute pre-composed validation workflows with one click.

### Key Capabilities

| Capability | Description |
|---|---|
| Device Discovery | Scan for Switchtec devices, connect with one click |
| Port Management | View link status, width, generation, and LTSSM state for all ports |
| Firmware Management | Inspect partitions, toggle active partition, manage boot RO flag |
| Event Monitoring | View and clear device events by category |
| Event Counters | Configure, read, and clear hardware event counters |
| Eye Diagrams | Capture eye diagrams with configurable resolution, view heatmaps and metrics |
| LTSSM Trace | Capture and visualize LTSSM state machine transitions |
| Performance | Live bandwidth monitoring and latency measurement |
| Workflows | 18 pre-composed validation recipes with live progress |
| Fabric Management | CSR read/write, GFMS bind/unbind, port control |
| Error Injection | Inject PCIe errors (DLLP CRC, TLP LCRC, etc.) and verify recovery |
| BER Testing | Loopback configuration, pattern generator/monitor, live error charts |
| Equalization | TX coefficients, FOM table, receiver calibration, cross-hair margin |
| Ordered Set Analyzer | Capture and analyze link training ordered sets |

### Launching the Dashboard

Start the Athena dashboard from the command line:

```
athena serve
```

The dashboard opens in your default browser at **http://localhost:8080**. All browser sessions share the same device connection (single-operator model). If you need to access the dashboard from another machine on the network, the NiceGUI server binds to all interfaces by default.

![Screenshot: Athena dashboard after launch, showing the Discovery page](screenshots/launch-discovery.png)

---

## 2. UI Overview

### Dark Theme

The Athena dashboard uses a **dark GitHub-inspired color palette** with the **JetBrains Mono** monospace font. This design reduces eye strain during extended lab sessions and provides high contrast for reading small numeric values.

| Element | Color | Hex Code |
|---|---|---|
| Accent (green) | Primary action color, active items | `#39d353` |
| Blue | Secondary accent, informational | `#58a6ff` |
| Purple | Tertiary accent | `#bc8cff` |
| Primary text | Body text, headings | `#e6edf3` |
| Secondary text | Subtitles, descriptions | `#8b949e` |
| Muted text | Placeholders, borders | `#484f58` |
| Primary background | Page background | `#0d1117` |
| Secondary background | Header, sidebar, card borders | `#161b22` |
| Card background | Card surfaces | `#1c2128` |
| Success | Link UP, passing values | `#66bb6a` |
| Warning | Elevated temperatures, cautions | `#ffa726` |
| Error | Link DOWN, failures, dangerous actions | `#ef5350` |

### Header Bar

The header bar spans the top of every page and contains:

1. **ATHENA logo** -- The Serial Cables logo image (32x32 px) followed by the word "ATHENA" in the accent green color with letter spacing.
2. **Subtitle** -- "Serial Cables Switchtec Switch Manager" in secondary text.
3. **Connected device context** (when a device is connected):
   - A memory icon colored by PCIe generation.
   - The device name (e.g., "PSX 48xG4").
   - A PCIe generation badge (e.g., "GEN4") with generation-specific color.
   - The die temperature (e.g., "65 C") in secondary text.
   - A **Disconnect** button (link_off icon) that drops the connection and returns you to the Discovery page.
4. **"No device"** label when no device is connected.
5. **Current page title** on the right side.

![Screenshot: Header bar with connected device showing name, Gen badge, and temperature](screenshots/ui-header-connected.png)

### Left Sidebar Navigation

The sidebar contains 15 navigation items, each with a Material Design icon. The active page is highlighted with:

- An **accent green left border** (3px solid).
- Bold text weight.
- The accent green color for both icon and label.
- A slightly elevated card background.

Inactive items appear in secondary text color with a transparent left border.

| Label | Route | Icon | Description |
|---|---|---|---|
| Discovery | `/` | search | Device scan and connection |
| Dashboard | `/dashboard` | dashboard | Switch overview and summary |
| Ports | `/ports` | device_hub | Port status table |
| Firmware | `/firmware` | system_update | Firmware partition management |
| Events | `/events` | notifications | Device event monitoring |
| Event Counters | `/evcntr` | bar_chart | Hardware event counter setup and read |
| Eye Diagram | `/eye` | visibility | Eye diagram capture and analysis |
| LTSSM Trace | `/ltssm` | timeline | LTSSM state machine trace |
| Performance | `/performance` | speed | Bandwidth and latency monitoring |
| Workflows | `/workflows` | play_circle | Pre-composed validation recipes |
| Fabric | `/fabric` | hub | Fabric topology and CSR access |
| BER Testing | `/ber` | science | Loopback, pattern gen/mon, live BER |
| Equalization | `/equalization` | tune | TX EQ coefficients and margin |
| Injection | `/injection` | warning | PCIe error injection |
| OSA | `/osa` | analytics | Ordered Set Analyzer |

![Screenshot: Left sidebar navigation with Ports page active](screenshots/ui-sidebar.png)

### Disconnected Guard

Every page except Discovery checks for an active device connection at load time. If no device is connected, the page displays a centered "No Device Connected" card with:

- A large `link_off` icon in muted gray.
- The heading "No Device Connected" in secondary text.
- The instruction "Go to Discovery to scan and connect to a Switchtec device."
- A **"Go to Discovery"** button that navigates you to the Discovery page (`/`).

This guard prevents accidental interaction with pages that require hardware access.

![Screenshot: Disconnected guard shown on the Dashboard page](screenshots/ui-disconnected.png)

### Color Conventions

#### PCIe Generation Colors

Each PCIe generation is assigned a distinct color used throughout the dashboard for badges, chart traces, and text highlighting:

| Generation | Color | Hex Code |
|---|---|---|
| Gen 1 | Gray | `#9e9e9e` |
| Gen 2 | Blue | `#42a5f5` |
| Gen 3 | Green | `#66bb6a` |
| Gen 4 | Orange | `#ffa726` |
| Gen 5 | Red | `#ef5350` |
| Gen 6 | Purple | `#ab47bc` |

#### Temperature Thresholds

Die temperature values are color-coded with three thresholds:

| Condition | Color | Threshold |
|---|---|---|
| Normal | Green (`#66bb6a`) | Below 70 C |
| Elevated | Yellow/Warning (`#ffa726`) | 70 C to 84 C |
| Critical | Red (`#ef5350`) | 85 C and above |

#### Link Status Colors

| State | Color | Hex Code |
|---|---|---|
| Link UP | Green | `#66bb6a` |
| Link Training | Yellow/Warning | `#ffa726` |
| Link DOWN | Red | `#ef5350` |

---

## 3. Discovery Page

**Route:** `/`
**Navigation label:** Discovery
**Icon:** search

The Discovery page is the landing page and starting point for all Athena sessions. You use it to find Switchtec devices on the system and establish a connection.

![Screenshot: Discovery page with device path input and scan/connect buttons](screenshots/discovery-page.png)

### Connect to Device Card

This card provides two methods for connecting to a device:

#### Manual Connection

1. Type a device path in the **Device Path** text field.
   - On Linux: `/dev/switchtec0`, `/dev/switchtec1`, etc.
   - On Windows: the appropriate device path for your system.
2. Click the **Connect** button (link icon, green).
3. On success, the dashboard navigates to the Dashboard page (`/dashboard`) and displays a green notification "Connected to [device name]".
4. On failure, an error message appears below the input field in red, and a notification banner displays the error detail.

The device path field accepts up to 256 characters. Paths are trimmed of leading and trailing whitespace.

#### Automatic Scan

1. Click the **Scan** button (search icon, blue).
2. Athena queries the system for all available Switchtec devices.
3. The button shows a loading spinner while the scan is in progress.
4. Results appear in the "Discovered Devices" card below.

### Discovered Devices Card

After a successful scan, each discovered device is displayed as a sub-card containing:

| Field | Example | Description |
|---|---|---|
| Device name | PSX 48xG4 | Model name of the Switchtec device |
| Description + PCI BDF | "Microsemi PSX 48xG4 \| 0000:03:00.0" | Device description and PCI bus/device/function |
| FW version + Path | "FW: 4.80 \| Path: /dev/switchtec0" | Firmware version and system path |
| **Connect** button | -- | One-click connection to this device |

If no devices are found, the card displays "No Switchtec devices found on this system."

![Screenshot: Discovered Devices card showing two devices with Connect buttons](screenshots/discovery-scan-results.png)

### Connection Workflow

1. Click **Scan** to discover devices, or type a path manually.
2. Click **Connect** on a discovered device (or the manual Connect button).
3. Athena opens the device, reads a summary (name, generation, temperature, port count), and caches it.
4. On success, you are navigated to the **Dashboard** page.
5. On failure, the error message appears inline and as a toast notification. Common causes: invalid path, device in use, permission denied.

---

## 4. Dashboard

**Route:** `/dashboard`
**Navigation label:** Dashboard
**Icon:** dashboard

The Dashboard page provides a high-level overview of the connected switch. It loads device summary data from the cached state (no I/O for the header) and asynchronously fetches port status for the port summary strip.

![Screenshot: Dashboard page showing summary cards, device details, and port badges](screenshots/dashboard-overview.png)

### Summary Stat Cards

Four stat cards appear at the top of the page in a horizontal row:

| Card | Content | Color Logic |
|---|---|---|
| **Temperature** | Die temperature in degrees C (e.g., "65.2 C") | Green below 70 C, yellow 70-84 C, red 85+ C |
| **Generation** | PCIe generation string (e.g., "GEN4") | Generation-specific color (see color conventions) |
| **Active Ports** | "X / Y" where X = linked-up ports, Y = total ports | Green if any port is up, red if all ports are down |
| **FW Version** | Firmware version string (e.g., "4.80") | Primary text color |

The Active Ports card initially shows "--" and updates asynchronously when the port status loads.

### Device Detail Card

Below the summary cards, a device detail card displays:

| Field | Example |
|---|---|
| Device ID | 0x4000 |
| Variant | PSX |
| Boot Phase | Main Firmware |
| FW Version | 4.80 |
| Temperature | 65.2 C |
| Ports | 48 |

The device name appears as the card heading with a generation badge and a memory icon colored by generation.

![Screenshot: Device detail card showing all fields](screenshots/dashboard-device-card.png)

### Port Summary Strip

The port summary appears as a row of compact badges, one per physical port. Each badge shows:

- **Port number** (e.g., "P0", "P12") in bold, colored by link status.
- **Status text** below the port number in smaller secondary text:
  - For linked ports: "x16 Gen4" (negotiated width and generation).
  - For training ports: the LTSSM state string (e.g., "Polling.Active").
  - For down ports: the LTSSM state string or "Down".

Badge borders are colored by link status:
- Green border for UP links.
- Yellow/orange border for ports in a training state (not in L0).
- Red border for DOWN links.

The background of each badge uses the secondary background color (`#161b22`) to provide contrast against the page.

![Screenshot: Port summary strip showing a mix of UP and DOWN ports](screenshots/dashboard-port-strip.png)

---

## 5. Ports Page

**Route:** `/ports`
**Navigation label:** Ports
**Icon:** device_hub

The Ports page presents a detailed table of all ports on the connected switch with sortable columns.

![Screenshot: Ports page showing the sortable port status table](screenshots/ports-table.png)

### Page Header

At the top of the page you see:
- The heading "Port Status".
- A subtitle line: "[Device Name] -- X of Y ports linked up" (e.g., "PSX 48xG4 -- 12 of 48 ports linked up").

### Port Table

The table contains the following columns. Columns marked "Sortable" can be sorted by clicking the column header.

| Column | Description | Sortable | Alignment |
|---|---|---|---|
| **Phys Port** | Physical port ID (0-based) | Yes | Center |
| **Log Port** | Logical port ID | Yes | Center |
| **Link** | Link status badge: green "UP" or red "DOWN" | No | Center |
| **Width** | Negotiated link width (e.g., "x16") or "--" if down | Yes | Center |
| **Gen** | PCIe generation (e.g., "Gen4") in generation-specific color, or "--" if down | Yes | Center |
| **LTSSM State** | Current LTSSM state string (e.g., "L0", "Polling.Active", "Detect.Quiet") | No | Left |
| **Cfg Width** | Configured (max) link width (e.g., "x16") | Yes | Center |
| **Lane Reversal** | Lane reversal status or "None" | No | Center |
| **BDF** | PCI Bus/Device/Function address or "--" | No | Left |

The **Link** column uses color-coded Quasar badges: green for UP and red for DOWN.

The **Gen** column renders the generation string in bold with the appropriate generation color (Gen1=gray through Gen6=purple).

### Refresh Button

Below the table, a **Refresh** button (refresh icon, blue outline) reloads the page to fetch fresh port status from the hardware.

### Empty State

If the device reports no port status data, the page displays a centered "No Ports Found" message with a device_hub icon.

---

## 6. Firmware Management

**Route:** `/firmware`
**Navigation label:** Firmware
**Icon:** system_update

The Firmware page displays firmware version information, boot configuration, and firmware partition details. It allows you to toggle the active partition and manage the boot read-only flag.

![Screenshot: Firmware page showing version cards, action buttons, and partition table](screenshots/firmware-overview.png)

### Stat Cards

Three stat cards appear at the top:

| Card | Content | Color Logic |
|---|---|---|
| **Firmware Version** | Firmware version string (e.g., "4.80") | Accent green |
| **Boot Phase** | Boot phase string (e.g., "Main Firmware") | Green for "Main Firmware"/"FW", yellow for "BL2", red for other |
| **Boot Read-Only** | "Enabled" or "Disabled" | Yellow if enabled (locked), green if disabled (unlocked) |

### Actions Card

The Actions card contains three buttons:

| Button | Icon | Color | Action |
|---|---|---|---|
| **Refresh** | refresh | Blue (primary) | Re-reads firmware data from device and updates all displays |
| **Toggle Active Partition** | swap_horiz | Yellow (warning) | Swaps the active firmware/config partition (requires confirmation) |
| **Toggle Boot RO** | lock / lock_open | Red (negative) | Toggles boot read-only flag (requires confirmation, dynamic label) |

The **Toggle Boot RO** button dynamically changes its label:
- When boot RO is currently enabled: "Disable Boot RO" with a lock_open icon.
- When boot RO is currently disabled: "Enable Boot RO" with a lock icon.

### Confirmation Dialogs

Both the Toggle Active Partition and Toggle Boot RO actions open confirmation dialogs before proceeding:

**Toggle Active Partition dialog:**
- Title: "Confirm Partition Toggle"
- Message: "This will toggle the active firmware and config partitions. The device may need to be reset for changes to take effect."
- Cancel (gray flat button) and Toggle (yellow button).

**Toggle Boot RO dialog:**
- Title: "Confirm Boot RO Change"
- Message: dynamically generated, e.g., "This will disable the boot partition read-only flag. This is a destructive operation."
- Cancel (gray flat button) and Confirm (red button).

### Partition Summary Table

The table displays all firmware partition slots:

| Column | Description | Alignment |
|---|---|---|
| **Partition** | Partition name (Boot, Map, Image, Config, NVLog, SEEPROM, Key, BL2, RIoT Core) | Left |
| **Slot** | Active or Inactive | Left |
| **Version** | Firmware version in this slot, or "-" | Left |
| **Gen** | Hardware generation | Center |
| **Valid** | "Yes" or "No" | Center |
| **Running** | "Yes" or "No" -- whether this partition is currently executing | Center |
| **RO** | "Yes" or "No" -- read-only flag | Center |
| **Address** | Partition start address in hex (e.g., "0x00000000") | Right |
| **Length** | Partition length in hex (e.g., "0x00040000") | Right |

#### Understanding Firmware Partitions

| Partition | Purpose |
|---|---|
| **Boot** | First-stage boot code executed from flash |
| **Map** | Flash memory layout descriptor |
| **Image** | Main firmware image (the running firmware) |
| **Config** | Device configuration data |
| **NVLog** | Non-volatile event log storage |
| **SEEPROM** | Serial EEPROM emulation area |
| **Key** | Cryptographic key storage |
| **BL2** | Second-stage bootloader |
| **RIoT Core** | Root of Trust (RIoT) attestation core |

Each partition can have an **Active** and **Inactive** slot. The Toggle Active Partition operation swaps which slot the device boots from. After toggling, you typically need to reset the device for the change to take effect.

![Screenshot: Partition Summary table with Active and Inactive slots](screenshots/firmware-partition-table.png)

---

## 7. Events Page

**Route:** `/events`
**Navigation label:** Events
**Icon:** notifications

The Events page displays a summary of device events broken down by category, with controls to refresh and clear all events.

![Screenshot: Events page showing summary cards and breakdown table](screenshots/events-overview.png)

### Summary Cards

Four stat cards display event counts:

| Card | Description | Color Logic |
|---|---|---|
| **Total Events** | Sum of all event categories | Green if 0, yellow if 1-9, red if 10+ |
| **Global Events** | Device-wide events | Green if 0, yellow if 1-9, red if 10+ |
| **Partition Events** | Partition-scoped events | Green if 0, yellow if 1-9, red if 10+ |
| **PFF Events** | Per-function (PFF) events | Green if 0, yellow if 1-9, red if 10+ |

### Actions

| Button | Icon | Color | Action |
|---|---|---|---|
| **Refresh** | refresh | Blue (primary) | Re-reads event summary from device |
| **Clear All Events** | delete_sweep | Red (negative) | Clears all event counters (requires confirmation) |

### Clear All Confirmation Dialog

- Title: "Confirm Clear All Events"
- Message: "This will clear all event counters on the device. This action cannot be undone."
- Cancel (gray flat) and Clear All (red) buttons.

### Event Breakdown Table

| Column | Description | Alignment |
|---|---|---|
| **Category** | "Global Events", "Partition Events", or "PFF Events" | Left |
| **Count** | Number of events in this category | Right |
| **Status** | "Clean" (green-implied, count is 0) or "Active" (count > 0) | Center |

---

## 8. Event Counters

**Route:** `/evcntr`
**Navigation label:** Event Counters
**Icon:** bar_chart

The Event Counters page provides low-level access to the Switchtec hardware event counter system. You can select counters, read their values, read their configuration, and program new counter configurations.

![Screenshot: Event Counters page showing selection, setup, and values table](screenshots/evcntr-overview.png)

### Counter Selection Card

This card controls which counters to read:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Stack ID** | Number | 0 - 7 | 0 | Switch stack (die) to query |
| **Counter ID** | Number | 0 - 63 | 0 | Starting counter index |
| **Number of Counters** | Number | 1 - 64 | 1 | How many consecutive counters to read |
| **Clear on Read** | Toggle | On/Off | Off | When enabled, counters are atomically cleared after reading |

> **Note:** The sum of Counter ID + Number of Counters must not exceed 64. The UI automatically clamps this.

Buttons:

| Button | Icon | Color | Action |
|---|---|---|---|
| **Read Counts** | analytics | Blue (primary) | Reads counter values (and optionally clears them) |
| **Read Setup** | settings | Gray (secondary) | Reads counter configuration without reading/clearing counts |

### Counter Setup Card

This card programs a single event counter:

| Parameter | Type | Default | Description |
|---|---|---|---|
| **Port Mask** | Number (hex) | 0 | Bitmask of ports to monitor |
| **Type Mask** | Number (hex) | 0 | Bitmask of event types to count |
| **Threshold** | Number | 0 | Threshold value for event triggering |
| **Egress** | Toggle | Off | When enabled, counts egress events; otherwise ingress |

Button:

| Button | Icon | Color | Action |
|---|---|---|---|
| **Apply Setup** | save | Green (positive) | Programs the counter with the specified configuration |

The counter being programmed is determined by the Stack ID and Counter ID from the Counter Selection card above.

### Counter Values Table

After reading counters, the results appear in a table:

| Column | Description | Alignment |
|---|---|---|
| **Counter ID** | Counter index | Center |
| **Count** | Current count value (or "-" if only setup was read) | Right |
| **Port Mask** | Hex bitmask of monitored ports | Center |
| **Type Mask** | Hex bitmask of monitored event types | Center |
| **Egress** | "Yes" or "No" | Center |
| **Threshold** | Configured threshold value | Right |

Before any read operation, the table shows the placeholder text "Click 'Read Counts' to load counter values."

---

## 9. Eye Diagram Capture

**Route:** `/eye`
**Navigation label:** Eye Diagram
**Icon:** visibility

The Eye Diagram page captures a 2D eye diagram for a specific port and lane, displays it as a Plotly heatmap, computes eye opening metrics, and supports BER read and data export.

![Screenshot: Eye Diagram page showing capture settings and a completed heatmap](screenshots/eye-overview.png)

### Capture Settings Card

#### Basic Settings

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Physical port to capture |
| **Lane ID** | Number | 0 - 143 | 0 | Lane within the port |

#### Step Configuration

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **X Step** | Number | 1 - 16 | 1 | Phase (horizontal) step size |
| **Y Step** | Number | 1 - 16 | 2 | Voltage (vertical) step size |
| **Step Interval** | Number | 1 - 1000 ms | 10 | Delay between capture steps in milliseconds |

#### Range Configuration

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **X Start** | Number | -128 to 0 | -64 | Phase range start |
| **X End** | Number | 0 to 128 | 64 | Phase range end |
| **Y Start** | Number | -511 to 0 | -255 | Voltage range start |
| **Y End** | Number | 0 to 511 | 255 | Voltage range end |

> **Tip:** Larger ranges and smaller step sizes produce higher-resolution eye diagrams but take longer to capture. A good starting point is the defaults: X from -64 to +64, Y from -255 to +255, with X step 1 and Y step 2.

#### Eye Data Mode

| Parameter | Options | Description |
|---|---|---|
| **Generation** | "Gen3-5 (NRZ)" or "Gen6 (PAM4)" | Selects the signaling family |
| **Data Mode** | RAW and other modes (varies by generation) | Controls how eye data is sampled |
| **Apply Mode** | Button | Sends the selected mode to the hardware |

When you change the Generation selector, the Data Mode dropdown updates to show the modes available for that generation family.

#### Capture Controls

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Capture** | play_arrow | Green (positive) | Begins the eye capture sequence |
| **Cancel** | stop | Red (negative) | Cancels a running capture (disabled when not capturing) |

### Progress Card

During capture, a progress card appears showing:

- A text label (e.g., "Fetching eye data... (45%)").
- A linear progress bar that fills from 0% to 100%.

The capture process:
1. Sends capture start parameters to the hardware.
2. Polls for completion up to 60 seconds (600 attempts at 100ms intervals).
3. On success, renders the eye diagram and metrics.
4. On timeout, shows "Capture timed out."
5. On cancellation, shows "Capture cancelled."

### Eye Diagram Result

The eye diagram renders as a **Plotly heatmap** with:

- **Colorscale:** "Hot" (red-yellow-white gradient), reversed so high hit counts appear warm.
- **X axis:** Phase (UI) -- horizontal eye opening.
- **Y axis:** Voltage (mV) -- vertical eye opening.
- **Title:** "Eye Diagram - Port [X] Lane [Y]".
- **Dark theme:** Background colors and font match the dashboard theme.

The heatmap uses the dark theme layout: `#1c2128` plot background, `#0d1117` paper background, and JetBrains Mono font.

![Screenshot: Rendered eye diagram heatmap showing a clear eye opening](screenshots/eye-heatmap.png)

### Eye Metrics Cards

After capture, three metric cards appear:

| Metric | Unit | Color | Description |
|---|---|---|---|
| **Eye Width** | phase steps | Green (`#39d353`) | Horizontal opening measured across the center row |
| **Eye Height** | voltage steps | Blue (`#58a6ff`) | Vertical opening measured down the center column |
| **Eye Area** | % open | Purple (`#bc8cff`) | Percentage of pixels below the 10% threshold (open eye area) |

The metrics are computed by:
1. Finding the peak pixel value.
2. Setting a threshold at 10% of peak.
3. Eye Width: longest contiguous run of below-threshold pixels in the center row.
4. Eye Height: longest contiguous run of below-threshold pixels in the center column.
5. Eye Area: fraction of all pixels below threshold, as a percentage.

### BER Read Section (Gen5+)

For Gen5 and Gen6 devices, you can read bit error rate data:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Lane ID** | Number | 0 - 143 | 0 | Lane to read |
| **Bin Index** | Number | 0 - 15 | 0 | BER bin index |
| **Max Phases** | Number | 1 - 256 | 60 | Maximum number of phase points to read |

Click **Read BER** to fetch the data. The result displays as a **Plotly scatter plot** with:
- X axis: Phase Index.
- Y axis: BER (logarithmic scale).
- Line color: accent green.
- Markers: 4px dots with 2px line width.

![Screenshot: BER scatter plot with log-scale Y axis](screenshots/eye-ber-plot.png)

### Export Section

Two export buttons allow you to download captured eye data:

| Button | Format | Filename | Description |
|---|---|---|---|
| **Export CSV** | CSV | `eye_lane[N].csv` | Comma-separated x,y,value rows |
| **Export JSON** | JSON | `eye_lane[N].json` | Structured JSON with lane_id, ranges, pixel data |

If no eye data has been captured yet, clicking either button shows a warning notification.

---

## 10. LTSSM Trace

**Route:** `/ltssm`
**Navigation label:** LTSSM Trace
**Icon:** timeline

The LTSSM Trace page captures and visualizes Link Training and Status State Machine (LTSSM) transitions for a specific port. LTSSM tracing is essential for debugging link training failures, unexpected link retraining, and understanding the sequence of states a link traverses during negotiation.

![Screenshot: LTSSM Trace page showing controls, timeline chart, and log entries](screenshots/ltssm-overview.png)

### What Is LTSSM and Why Trace It

The PCIe LTSSM governs link initialization and operation. Every link transition (e.g., Detect -> Polling -> Configuration -> L0) is a state change. When a link fails to train, analyzing the sequence of LTSSM states helps identify where the process stalls. Common states include:

- **Detect.Quiet / Detect.Active** -- Initial link detection.
- **Polling.Active / Polling.Configuration** -- Lane polarity and bit-lock.
- **Configuration** -- Link width and lane negotiation.
- **L0** -- Normal operational state (link is UP).
- **Recovery** -- Link retraining after error.
- **L1 / L2** -- Low power states.

### Controls

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Physical port to trace |
| **Max Entries** | Number | 1 - 256 | 64 | Maximum number of log entries to capture |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Capture Log** | history | Blue (primary) | Reads the LTSSM transition log from hardware |
| **Clear Log** | delete | Red (negative) | Clears the LTSSM log on the device for the selected port |

### LTSSM Timeline Chart

After capturing, the timeline renders as a **Plotly scatter-step chart**:

- **X axis:** Timestamp (from the hardware log).
- **Y axis:** State ID (numeric LTSSM state code).
- **Hover:** Shows the human-readable LTSSM state name.
- **Line style:** Step trace (preserving the discrete nature of state transitions).

This visualization makes it easy to see:
- How long the link spent in each state.
- Whether the link oscillated between states (indicating a training failure).
- The exact transition sequence.

![Screenshot: LTSSM timeline chart showing state transitions over time](screenshots/ltssm-timeline.png)

### Log Entries Table

Below the timeline, a paginated table (20 rows per page) displays the raw log data:

| Column | Description | Sortable | Alignment |
|---|---|---|---|
| **Timestamp** | Hardware timestamp of the transition | Yes | Left |
| **LTSSM State** | Human-readable state name (e.g., "L0", "Recovery.RcvrLock") | Yes | Left |
| **State ID** | Numeric state identifier | Yes | Right |
| **Link Rate** | Negotiated link rate at this transition | Yes | Right |
| **Width** | Negotiated width at this transition | Yes | Right |
| **TX Minor** | TX minor state code | Yes | Right |
| **RX Minor** | RX minor state code | Yes | Right |

---

## 11. Performance Monitoring

**Route:** `/performance`
**Navigation label:** Performance
**Icon:** speed

The Performance page provides two measurement tools: live bandwidth monitoring and latency measurement.

![Screenshot: Performance page showing bandwidth chart and latency results](screenshots/performance-overview.png)

### Bandwidth Monitoring

#### Configuration

| Parameter | Type | Options | Description |
|---|---|---|---|
| **Ports to Monitor** | Multi-select | All ports (labeled "PX (UP)" or "PX (DOWN)") | Select one or more ports to track; uses chip display for selected items |
| **Interval** | Select | 1s, 2s, 5s | Polling frequency |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Monitoring** | play_arrow | Green (positive) | Begins periodic bandwidth polling |
| **Stop Monitoring** | stop | Red (negative) | Stops the polling timer (disabled when not monitoring) |

When monitoring is active:
- The port selector and interval selector are disabled (locked).
- The Start button is disabled; the Stop button is enabled.

#### Live Bandwidth Chart

A Plotly time-series chart updates on each poll tick:

- **X axis:** Elapsed time in seconds.
- **Y axis:** Bytes transferred.
- **Per-port traces:** Each selected port gets two traces:
  - **Egress** (solid line) -- data leaving the port.
  - **Ingress** (dashed line) -- data entering the port.
- **Colors:** Up to 12 distinct colors are available. Ports cycle through: light blue, green, orange, red, purple, cyan, yellow, pink, brown, gray, lime, blue.
- **Data retention:** Up to 120 data points per port are kept in memory. Older points scroll off the left edge.

![Screenshot: Live bandwidth chart with two ports showing egress and ingress traces](screenshots/performance-bandwidth-chart.png)

#### Current Bandwidth Totals

Below the chart, per-port bandwidth total cards update on each tick:

- **Port number** in accent green.
- **Egress:** total bytes with comma formatting (e.g., "1,234,567 B").
- **Ingress:** total bytes with comma formatting.
- **Egress Mbps** and **Ingress Mbps** calculated from byte count and elapsed time.

### Latency Measurement

#### Configuration

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Egress Port ID** | Number | 0 - 59 | 0 | Port where traffic originates |
| **Ingress Port ID** | Number | 0 - 59 | 0 | Port where traffic arrives |
| **Samples** | Number | 1 - 100 | 10 | Number of latency measurements to collect |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Measure Latency** | timer | Blue (primary) | Runs the latency measurement |

#### Measurement Process

1. Athena sets up the latency counter pair (egress -> ingress).
2. Collects the specified number of samples sequentially.
3. Computes statistics from the collected data.

#### Results

Three stat cards display aggregate results:

| Card | Value | Color |
|---|---|---|
| **Average** | Average of all "current" readings in nanoseconds | Accent green |
| **Min** | Minimum "current" reading in nanoseconds | Green (success) |
| **Peak** | Maximum "max" reading across all samples in nanoseconds | Yellow (warning) |

Below the stat cards, a sortable table lists every sample:

| Column | Description | Sortable | Alignment |
|---|---|---|---|
| **#** | Sample number (1-based) | No | Right |
| **Current (ns)** | Latency measured for this sample | Yes | Right |
| **Max (ns)** | Maximum latency observed in this measurement window | Yes | Right |

The table is paginated at 20 rows per page.

![Screenshot: Latency results showing stat cards and sample table](screenshots/performance-latency.png)

---

## 12. Workflows

**Route:** `/workflows`
**Navigation label:** Workflows
**Icon:** play_circle

The Workflows page provides 18 pre-composed validation recipes organized into six categories. Each recipe automates a multi-step test sequence, reports per-step results in real time, and produces a final PASS/FAIL/WARN summary.

![Screenshot: Workflows page showing category tabs and recipe cards](screenshots/workflows-overview.png)

### Category Tabs

Six category tabs appear at the top of the page:

| Category | Icon | Description |
|---|---|---|
| **Link Health** | monitor_heart | Link status, training, and LTSSM monitoring |
| **Signal Integrity** | ssid_chart | Eye diagrams, margins, and equalization |
| **Error Testing** | bug_report | BER soak, loopback sweep, error injection |
| **Performance** | speed | Bandwidth, latency, and event counter baselines |
| **Configuration** | settings | Config space, firmware, and fabric validation |
| **Debug** | pest_control | OSA captures and thermal profiling |

Click a tab to view the recipes in that category.

### Recipe Cards

Each implemented recipe displays as a card containing:

1. **Recipe name** in bold (e.g., "All-Port Status Sweep").
2. **Duration badge** showing estimated runtime (e.g., "~3s").
3. **Description** in secondary text explaining what the recipe does.
4. **Parameter inputs** auto-generated from the recipe's parameter definitions (number inputs, toggles, selects).
5. **Run** button (green, play_arrow icon).

Recipes that are not yet implemented appear as disabled (grayed-out) scaffold cards with a "Coming soon" tooltip.

![Screenshot: Recipe card with parameter inputs and Run button](screenshots/workflows-recipe-card.png)

### Recipe Runner Panel

When you click **Run** on a recipe card, the Recipe Runner panel activates:

1. **Status label** shows "Running: [Recipe Name]..."
2. **Cancel** button appears (red, flat style).
3. **RecipeStepper** renders each step as it completes:
   - A spinner icon for the currently running step.
   - A green check icon for passed steps.
   - A red X icon for failed steps.
   - A yellow warning icon for steps with warnings.
   - A gray skip icon for skipped steps.
   - Step label format: "[1/3] Step Name".
   - Detail text in secondary color.

When the recipe completes, the stepper renders a **summary banner**:

| Outcome | Banner Color | Icon | Text |
|---|---|---|---|
| All steps pass | Green | check_circle | "[Recipe Name]: Passed" |
| Some warnings | Yellow | warning | "[Recipe Name]: Passed with Warnings" |
| Any failure | Red | error | "[Recipe Name]: Failed" |
| Cancelled | Yellow | cancel | "[Recipe Name]: Aborted" |

The summary also shows counts: Passed, Failed, Warnings, Skipped, and elapsed Time.

![Screenshot: Recipe Runner showing live step progress and summary banner](screenshots/workflows-runner.png)

### Complete Recipe Reference

The following table lists all 18 implemented recipes with their category, name, description, estimated duration, and configurable parameters.

#### Link Health Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 1 | **All-Port Status Sweep** | ~3s | Scan every port on the switch for link status, width, rate, LTSSM state, and die temperature. | None |
| 2 | **Link Health Check** | ~2s | Check a single port's link status, negotiated width and rate, and read die temperature. | Port ID (0-59, default 0) |
| 3 | **Link Training Debug** | ~5s | Debug link training issues by reading port status, LTSSM state, and LTSSM transition log for a single port. | Port ID (0-59, default 0) |
| 4 | **LTSSM State Monitor** | 30s (configurable) | Clear the LTSSM log, monitor for state transitions over a configurable duration, and report any detected transitions. | Port ID (0-59, default 0), Duration in seconds (5-300, default 30) |

#### Signal Integrity Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 5 | **Eye Diagram Quick Scan** | ~30s | Capture a quick eye diagram for a single lane, compute eye width, height, and open area metrics. | Port ID, Lane ID |
| 6 | **Cross-Hair Margin Analysis** | ~10s/lane | Enable cross-hair measurement on one or more lanes, poll until complete, and report horizontal and vertical eye margins. | Start Lane, Number of Lanes |
| 7 | **Port Equalization Report** | ~3s | Read TX equalization coefficients, EQ table, and FS/LF values for a port's lanes. | Port ID |

#### Error Testing Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 8 | **BER Soak Test** | 60s (configurable) | Run a pattern generator for a configurable duration and measure bit error rate. Checks for link retraining during the soak. | Port ID, Duration, Link Speed |
| 9 | **Loopback BER Sweep** | varies | Enable loopback and sweep all PRBS patterns for the selected generation. Identifies the weakest pattern and worst-case BER. | Port ID, Generation |
| 10 | **Error Injection + Recovery** | ~5s | Inject a PCIe error on a port and monitor link recovery and LTSSM transitions. | Port ID |

#### Performance Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 11 | **Bandwidth Baseline** | 10s (configurable) | Sample bandwidth counters on a port over a configurable duration and compute min/max/avg statistics. | Port ID, Duration |
| 12 | **Latency Measurement Profile** | ~5s | Measure switch latency between egress and ingress ports, collecting multiple samples to compute min/max/avg. | Egress Port, Ingress Port, Sample Count |
| 13 | **Event Counter Stress Baseline** | 30s (configurable) | Configure an event counter, soak for a duration, and report total events and event rate. | Stack ID, Counter ID, Duration |

#### Configuration Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 14 | **Config Space Dump** | ~2s | Dump device summary and port configuration for a single port. | Port ID |
| 15 | **Firmware Validation** | ~2s | Validate firmware version, partition integrity, and boot read-only status. | None |
| 16 | **Fabric Bind/Unbind Validation** | ~5s | Validate fabric bind and unbind operations by performing a round-trip bind/unbind cycle and verifying port config. | Host SW Index, Phys Port, Log Port |

#### Debug Recipes

| # | Recipe Name | Duration | Description | Parameters |
|---|---|---|---|---|
| 17 | **OSA Link Training Capture** | ~10s | Configure and run an OSA (Ordered Set Analyzer) capture to record link training ordered sets. | Stack ID, Lane ID |
| 18 | **Switch Thermal Profile** | 60s (configurable) | Monitor die temperature sensors over time and report per-sensor min/max/avg statistics. | Duration |

---

## 13. Fabric / Topology Management

**Route:** `/fabric`
**Navigation label:** Fabric
**Icon:** hub

The Fabric page provides low-level fabric topology management for PAX (fabric-capable) Switchtec devices. It includes port configuration reads, CSR (Configuration Space Register) access, GFMS bind/unbind operations, port control, and GFMS event management.

> **WARNING:** Operations on this page directly modify hardware state. CSR writes, bind/unbind operations, and port control can cause link disruptions, data loss, and system instability. Use only in controlled test environments. All destructive operations require explicit confirmation.

![Screenshot: Fabric page showing Port Configuration, CSR, and Bind/Unbind sections](screenshots/fabric-overview.png)

### Port Configuration

Read the configuration of a physical port:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Physical Port ID** | Number | 0 - 59 | 0 | Port to query |

Click **Get Config** to read. The result displays as a card showing:

| Field | Description |
|---|---|
| Port Type | The port's type classification |
| Clock Source | Clock source configuration |
| Clock SRIS | Separate Refclock with Independent SSC status |
| HVD Instance | Hardware Virtualization Domain instance |

### CSR Read / Write

Read or write Configuration Space Registers:

#### Read Parameters

| Parameter | Type | Description |
|---|---|---|
| **PDFID** | Number (0-65535) | Physical Device Function ID to target |
| **Address (hex)** | Text | Register address in hexadecimal (e.g., "0x00", "0x100") |
| **Width** | Select: 8-bit, 16-bit, 32-bit | Access width |

Click **Read CSR** to read the register. The result appears below as: `CSR[0x100] (w32) = 0x12345678`.

#### Write Parameters

| Parameter | Type | Description |
|---|---|---|
| **Write Value (hex)** | Text | Value to write in hexadecimal |

Click **Write CSR** to write. A confirmation dialog appears:

> **WARNING:** CSR writes are dangerous. Writing to config space registers can cause hardware malfunction. The confirmation dialog uses a **red** confirm button to indicate the destructive nature.

- Title: "Confirm CSR Write"
- Message: "Write 0x[value] to CSR address [addr] (w[width])? Writing to config space registers can cause hardware malfunction."

### GFMS Bind

Bind an endpoint to a host through the fabric:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Host SW Index** | Number | 0 - 255 | 0 | Host switch index |
| **Phys Port** | Number | 0 - 255 | 0 | Physical port ID |
| **Log Port** | Number | 0 - 255 | 0 | Logical port ID |
| **EP Number** | Number | 0+ | 0 | Endpoint number |
| **EP PDFIDs** | Text | Comma-separated | -- | Endpoint Physical Device Function IDs (e.g., "0,1,2") |

Click **Bind** to execute. A confirmation dialog appears:
- "Binding changes fabric topology. This may disrupt active connections."
- Red confirm button.

### GFMS Unbind

Remove an endpoint binding:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Host SW Index** | Number | 0 - 255 | 0 | Host switch index |
| **Phys Port** | Number | 0 - 255 | 0 | Physical port ID |
| **Log Port** | Number | 0 - 255 | 0 | Logical port ID |
| **PDFID** | Number | 0 - 65535 | 0 | Physical Device Function ID |
| **Option** | Number | 0 - 255 | 0 | Unbind option flags |

Click **Unbind** to execute. A confirmation dialog appears:
- "Unbinding removes fabric connections. Active traffic will be disrupted."
- Red confirm button.

### Port Control

Execute control actions on a physical port:

| Parameter | Type | Options | Description |
|---|---|---|---|
| **Physical Port ID** | Number (0-59) | -- | Target port |
| **Action** | Select | Enable, Disable, Hot Reset | Control action |

Click **Execute** to run. A confirmation dialog appears:
- "Execute '[action]' on port [id]? Port control operations can disrupt active links."
- Red confirm button.

### GFMS Events

A single **Clear GFMS Events** button (delete_sweep icon, yellow) clears all GFMS events on the device. This requires confirmation:
- "Clear all GFMS events on the device?"
- Red confirm button.

---

## 14. Error Injection

**Route:** `/injection`
**Navigation label:** Injection
**Icon:** warning

The Error Injection page allows you to inject PCIe errors into specific ports, generate AER events, and verify link recovery after injection. This is a critical tool for testing error handling and recovery mechanisms.

![Screenshot: Error Injection page showing warning banner and injection controls](screenshots/injection-overview.png)

### Warning Banner

A prominent red-bordered warning card appears at the top of the page:

> **Error Injection - Use With Caution**
>
> Error injection can cause link failures, data corruption, and system instability. Only use in controlled test environments.

### Inject Error Section

| Parameter | Type | Options | Default | Description |
|---|---|---|---|---|
| **Physical Port ID** | Number | 0 - 59 | 0 | Target port for injection |
| **Injection Type** | Select | See table below | DLLP CRC | Type of error to inject |

#### Injection Types and Context-Sensitive Parameters

| Injection Type | Additional Parameters | Description |
|---|---|---|
| **DLLP CRC** | Enable (toggle), Rate (number) | Injects CRC errors into Data Link Layer Packets |
| **TLP LCRC** | Enable (toggle), Rate (number) | Injects LCRC errors into Transaction Layer Packets |
| **Sequence Number** | None | Injects a single sequence number error |
| **ACK/NACK** | Sequence Number, Count | Injects ACK/NACK protocol errors |
| **Completion Timeout** | None | Forces a completion timeout condition |
| **Raw DLLP** | DLLP Data (hex) | Injects a raw DLLP with arbitrary data |

The parameter fields dynamically show/hide based on the selected injection type. For example, the Enable toggle and Rate field only appear for DLLP CRC and TLP LCRC types.

Click **Inject** (bolt icon, red) to inject. A confirmation dialog appears:
- "Inject [Type] error on port [N]? This may cause link degradation or failure."
- Red confirm button.

### AER Event Generation

Generate Advanced Error Reporting events:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Target port |
| **Error ID** | Number | 0+ | 0 | AER error identifier |
| **Trigger** | Number | 0+ | 0 | Trigger value for the event |

Click **Generate AER Event** (error_outline icon, red) to generate. A confirmation dialog appears:
- "Generate AER event (error_id=[N]) on port [N]? AER events may trigger system-level error handling."
- Red confirm button.

### Post-Injection Link Verification

After injecting errors, you can verify link status and recovery:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Port to verify |
| **Duration (s)** | Number | 1 - 30 | 5 | Monitoring duration in seconds |

Click **Run Verification** (verified icon, blue) to begin. The verification process:

1. **Captures pre-injection link state** (UP or DOWN).
2. **Clears the LTSSM log** for the port.
3. **Monitors link status** by polling every 0.5 seconds for the specified duration.
4. **Detects link-down events** and link recovery.
5. **Captures post-verification link state**.
6. **Reads the LTSSM transition log**.
7. **Renders results.**

#### Verification Results

**Pre/Post link badges:** Colored badges showing link UP (green) or DOWN (red) before and after verification.

**Verdict banner:** A color-coded verdict card:

| Verdict | Color | Icon | Condition |
|---|---|---|---|
| **Link Stable** | Green | check_circle | Link stayed UP, no LTSSM transitions |
| **Link Stable (LTSSM activity: N transitions)** | Yellow | info | Link stayed UP but LTSSM transitions were detected |
| **Link Recovered (X.Xs)** | Yellow | replay | Link went down but recovered; shows recovery time |
| **Link Down** | Red | error | Link is down after verification |

**LTSSM timeline:** If any LTSSM transitions were detected during the verification window, the LTSSM timeline chart renders below the verdict.

![Screenshot: Verification results showing Pre/Post badges, verdict, and LTSSM timeline](screenshots/injection-verification.png)

### Injection History Table

All injections during the current session are logged in a table at the bottom of the page:

| Column | Description | Alignment |
|---|---|---|
| **Time (UTC)** | Timestamp of the injection (HH:MM:SS format) | Left |
| **Type** | Injection type label (e.g., "DLLP CRC", "AER Event") | Left |
| **Port** | Target port ID | Center |
| **Details** | Injection parameters (e.g., "enable=True, rate=1") | Left |

> **Note:** The injection history is stored in memory and is not persisted across page reloads or sessions.

---

## 15. BER Testing

**Route:** `/ber`
**Navigation label:** BER Testing
**Icon:** science

The BER Testing page provides a comprehensive bit error rate testing environment with loopback configuration, pattern generation, pattern monitoring, inline error injection, and live error charting.

![Screenshot: BER Testing page showing all sections](screenshots/ber-overview.png)

### Master Port Selector

At the top of the page, a **Target Port** selector (Port ID, 0-59) syncs its value to all port input fields across every section on this page. Changing the master port automatically updates all section port fields.

### Loopback Configuration

Configure the physical-layer loopback mode for a port:

| Parameter | Type | Options / Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 (synced to master) | Target port |
| **LTSSM Speed** | Select | GEN1 through GEN6 | GEN4 | Link speed for LTSSM loopback |
| **Parallel** | Toggle | On/Off | Off | Enable parallel loopback |
| **External** | Toggle | On/Off | Off | Enable external loopback |
| **LTSSM** | Toggle | On/Off | Off | Enable LTSSM loopback |
| **PIPE** | Toggle | On/Off | Off | Enable PIPE-level loopback |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Enable Loopback** | loop | Green (positive) | Enables loopback with selected options |
| **Disable Loopback** | close | Red (negative) | Disables loopback on the port |
| **Read Status** | refresh | Flat | Reads current loopback status from hardware |

The status label below the buttons shows the current state, e.g., "Loopback ENABLED on port 0 at GEN4" (green text) or "Loopback DISABLED on port 0" (gray text).

### Pattern Generator

Generate PRBS test patterns on a port:

| Parameter | Type | Options | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 (synced to master) | Target port |
| **PCIe Generation** | Select | Gen 3, Gen 4, Gen 5, Gen 6 | Gen 4 | Determines available patterns |
| **Pattern** | Select | Varies by generation (see table) | PRBS31 | Test pattern type |
| **Link Speed** | Select | GEN1 through GEN6 | GEN4 | Transmission speed |

#### Available Patterns by Generation

| Generation | Patterns |
|---|---|
| **Gen 3** | PRBS7, PRBS11, PRBS23, PRBS31, PRBS9, PRBS15, Disabled |
| **Gen 4** | PRBS7, PRBS11, PRBS23, PRBS31, PRBS9, PRBS15, Disabled |
| **Gen 5** | PRBS7, PRBS11, PRBS23, PRBS31, PRBS9, PRBS15, PRBS5, PRBS20, Disabled |
| **Gen 6** | PRBS7, PRBS9, PRBS11, PRBS13, PRBS15, PRBS23, PRBS31, 52UI Jitter, Disabled |

When you change the Generation selector, the Pattern dropdown updates to show the patterns available for that generation.

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Generator** | play_arrow | Green (positive) | Starts the pattern generator |
| **Stop Generator** | stop | Red (negative) | Stops the pattern generator (sends "Disabled" pattern) |

### Pattern Monitor

Monitor received patterns and count errors:

| Parameter | Type | Options / Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 (synced to master) | Target port |
| **Lane Count** | Number | 1 - 16 | 4 | Number of lanes to monitor |
| **Poll Interval** | Select | 0.5s, 1s, 2s, 5s, 10s | 1s | How often to poll error counts |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Monitoring** | play_arrow | Green (positive) | Begins periodic error count polling |
| **Stop Monitoring** | stop | Red (negative) | Stops the polling timer |

When monitoring is active, the port, lane count, and interval controls are disabled.

#### Inline Error Injection

While the pattern monitor is running, you can inject errors into the pattern stream:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 (synced to master) | Injection port |
| **Error Count** | Number | 1 - 1000 | 1 | Number of errors to inject |

Click **Inject Errors** (bolt icon, red). A confirmation dialog appears: "Inject [N] error(s) into pattern stream on port [N]?"

### Per-Lane Error Count Table

The table updates on each poll tick:

| Column | Description | Sortable | Alignment |
|---|---|---|---|
| **Lane** | Lane index (0-based) | No | Center |
| **Pattern Type** | Detected pattern type on this lane | No | Center |
| **Error Count** | Cumulative error count | Yes | Right |
| **Delta** | Errors since last poll | No | Right |
| **BER (approx)** | Approximate BER calculated from errors / (GT/s x elapsed time) | No | Right |

The BER approximation uses the selected Pattern Generator link speed to compute total bits transferred.

### Live BER Error Count Chart

A Plotly time-series chart displays error counts over time:

- **X axis:** Elapsed time in seconds.
- **Y axis:** Error count (cumulative).
- **Traces:** One line per lane, each in a distinct color (up to 16 lanes supported).
- **Data retention:** Up to 120 data points per lane.
- **Dark theme:** Matches the dashboard color palette.

This chart helps you visualize error accumulation rates and identify lanes with degraded signal quality.

![Screenshot: Live BER chart showing per-lane error counts over time](screenshots/ber-live-chart.png)

### BER Testing Methodology

A typical BER test workflow:

1. **Enable loopback** on the target port (or connect an external loopback plug).
2. **Start the pattern generator** with the desired PRBS pattern and link speed.
3. **Start the pattern monitor** with the appropriate lane count.
4. **Observe error counts** over time. A healthy link should show zero errors.
5. **Optionally inject errors** to verify that the monitor detects them.
6. **Stop monitoring** and **stop the generator** when done.
7. **Disable loopback** if enabled.

The approximate BER is calculated as:

```
BER = Error Count / (Link Rate in GT/s * 10^9 * Elapsed Seconds)
```

For example, at Gen4 (16 GT/s), 10 errors in 60 seconds yields: `BER = 10 / (16e9 * 60) = ~1.04e-11`.

---

## 16. Equalization & Margin

**Route:** `/equalization`
**Navigation label:** Equalization
**Icon:** tune

The Equalization & Margin page provides tools for reading TX equalization coefficients, FOM (Figure of Merit) tables, receiver calibration data, and performing cross-hair margin measurements.

![Screenshot: Equalization page showing TX coefficients chart and cross-hair results](screenshots/equalization-overview.png)

### TX Equalization Coefficients

Read and visualize TX equalization pre-cursor and post-cursor coefficients across all lanes:

| Parameter | Type | Options | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Target port |
| **End** | Select | Local, Remote | Local | Which end of the link to read |
| **Link** | Select | Current, Previous | Current | Current or previous link training result |
| **Prev Speed** | Select | Current, Gen3 (8 GT/s), Gen4 (16 GT/s), Gen5 (32 GT/s) | Current | Speed to read from (for previous link data) |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Read Coefficients** | download | Blue (primary) | Reads TX coefficients for all lanes |
| **Read FS/LF** | straighten | Flat | Reads Full Swing and Low Frequency values |

#### Coefficients Chart

After reading, a **grouped bar chart** displays:
- **X axis:** Lane number.
- **Blue bars:** Pre-cursor values.
- **Green bars:** Post-cursor values.
- **Title:** "TX Coefficients - Port [N] ([End], [Link])".

#### FS/LF Values

After reading FS/LF, two stat cards display:
- **FS** (Full Swing) in accent green.
- **LF** (Low Frequency) in blue.

### FOM Table

Read the equalization Figure of Merit table:

| Parameter | Type | Options | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Target port |
| **Link** | Select | Current, Previous | Current | Link state |
| **Prev Speed** | Select | Current, Gen3, Gen4, Gen5 | Current | Speed context |

Click **Read FOM Table** to load. The result is a paginated table (20 rows per page):

| Column | Description | Sortable |
|---|---|---|
| **Step#** | Equalization step index | No |
| **Pre** | Pre-cursor value | No |
| **Post** | Post-cursor value | No |
| **FOM** | Figure of Merit score | Yes |
| **Pre Up** | Pre-cursor up value | No |
| **Post Up** | Post-cursor up value | No |
| **Error** | Error status | No |
| **Active** | Active status | No |
| **Speed** | Link speed for this step | No |

### Receiver Calibration

Read receiver calibration and DFE (Decision Feedback Equalization) tap data:

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Port ID** | Number | 0 - 59 | 0 | Target port |
| **Lane ID** | Number | 0 - 143 | 0 | Specific lane |
| **Link** | Select | Current, Previous | Current | Link state |

Click **Read Receiver** to load. The results include:

**Stat cards:**

| Metric | Color |
|---|---|
| CTLE | Accent green |
| Target Amplitude | Blue |
| Speculative DFE | Purple |
| CTLE2 RX Mode | Yellow (warning) |

**DTCLK cards:**

| Metric |
|---|
| DTCLK[5] |
| DTCLK[8:6] |
| DTCLK[9] |

**DFE Taps bar chart:** A Plotly bar chart showing each DFE tap value (Tap 0, Tap 1, etc.) in accent green.

![Screenshot: Receiver calibration showing stat cards and DFE taps chart](screenshots/equalization-receiver.png)

### Cross-Hair Margin

The cross-hair margin measurement determines the horizontal (phase) and vertical (voltage) eye margins for one or more lanes. This is a quantitative margin assessment.

> **Caution:** Cross-hair measurement temporarily affects the lane under test. A yellow warning banner appears above the controls.

| Parameter | Type | Range | Default | Description |
|---|---|---|---|---|
| **Start Lane ID** | Number | 0 - 143 | 0 | First lane to measure |
| **Number of Lanes** | Number | 1 - 16 | 1 | How many consecutive lanes to measure |

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Measurement** | play_arrow | Green (positive) | Enables cross-hair and begins polling |
| **Stop** | stop | Red (negative) | Stops measurement and disables cross-hair |

#### Measurement Process

1. Click **Start Measurement** to enable cross-hair on the starting lane.
2. The UI polls every 1 second for measurement state.
3. The progress label shows current states (e.g., "States: MEASURING, MEASURING").
4. When all lanes reach DONE (or ERROR), polling stops and results render.
5. Cross-hair is automatically disabled on completion.

#### Results Table

| Column | Description | Alignment |
|---|---|---|
| **Lane** | Lane ID | Center |
| **State** | Measurement state (DONE or ERROR) | Center |
| **H Margin** | Horizontal margin (left + right phase steps) | Right |
| **V Margin** | Vertical margin (top + bottom voltage steps) | Right |
| **Verdict** | PASS or FAIL | Center |
| **Left** | Left phase limit | Right |
| **Right** | Right phase limit | Right |
| **Bot-Left** | Bottom-left voltage limit | Right |
| **Bot-Right** | Bottom-right voltage limit | Right |
| **Top-Left** | Top-left voltage limit | Right |
| **Top-Right** | Top-right voltage limit | Right |

**Pass/fail thresholds:**
- **Horizontal:** H Margin >= 20 phase steps.
- **Vertical:** V Margin >= 30 voltage steps.
- A lane passes only if both thresholds are met.

A summary line below the table shows:
- "All N lane(s) PASS margin thresholds (H >= 20, V >= 30)" in green, or
- "N lane(s) FAIL margin thresholds (H >= 20, V >= 30)" in red.

> **Note:** These are conservative Gen4 NRZ defaults. Gen6 PAM4 eyes have smaller openings and may require different thresholds for your specific validation criteria.

#### Margin Diamond Visualization

For lanes that completed successfully, a **Plotly polygon chart** renders the margin diamond:

- Each lane is drawn as a diamond-shaped polygon: (0, top) -> (right, 0) -> (0, bottom) -> (left, 0) -> (0, top).
- Each lane gets a distinct fill color (semi-transparent) and border color.
- **X axis:** Horizontal (phase steps).
- **Y axis:** Vertical (voltage steps), with equal axis scaling.
- The chart provides an intuitive visual comparison of margin sizes across lanes.

![Screenshot: Margin diamond visualization showing per-lane eye opening polygons](screenshots/equalization-margin-diamond.png)

---

## 17. Ordered Set Analyzer

**Route:** `/osa`
**Navigation label:** OSA
**Icon:** analytics

The Ordered Set Analyzer (OSA) page configures and captures ordered sets transmitted during PCIe link training. This is an advanced debug tool for analyzing the low-level negotiation protocol between link partners.

![Screenshot: Ordered Set Analyzer page showing configuration and capture controls](screenshots/osa-overview.png)

### OSA Configuration

#### Basic Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| **Stack ID** | Number | 0 | Switch stack (die) |
| **Lane ID** | Number | 0 | Lane to analyze |
| **Direction** | Select: RX, TX | RX | Capture direction |
| **Lane Mask (hex)** | Text | 0x1 | Bitmask of lanes to include |
| **Link Rate** | Number | 0 | Link rate index |

#### Type Filter

Configure which ordered set types to capture:

| Parameter | Type | Default | Description |
|---|---|---|---|
| **OS Types (hex bitmask)** | Text | 0xFFFF | Bitmask of OS types to accept |

Click **Apply Type Config** to send the type filter to hardware.

#### Pattern Match

Configure pattern-based filtering:

| Parameter | Type | Default | Description |
|---|---|---|---|
| **Pattern Value (4 hex DWORDs, comma-sep)** | Text | 0,0,0,0 | Four 32-bit values to match |
| **Pattern Mask (4 hex DWORDs, comma-sep)** | Text | 0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF | Bitmask for pattern matching |

Click **Apply Pattern Config** to send the pattern filter to hardware.

### Capture Controls

| Button | Icon | Color | Action |
|---|---|---|---|
| **Start Capture** | play_arrow | Green (positive) | Begins the OSA capture on the selected stack |
| **Stop Capture** | stop | Red (negative) | Stops the running capture |

#### Capture Control Parameters

Fine-tune capture behavior:

| Parameter | Type | Default | Description |
|---|---|---|---|
| **Drop Single OS** | Number (0 or 1) | 0 | Drop single-occurrence ordered sets |
| **Stop Mode** | Number | 0 | When to stop capture |
| **Snapshot Mode** | Number | 0 | Snapshot behavior |
| **Post Trigger** | Number | 0 | Post-trigger capture depth |
| **OS Types (hex)** | Text | 0x0 | OS type filter for capture control |

Click **Apply Capture Control** to program these parameters.

Click **Fetch Capture Data** to download the captured data from the hardware. The result displays as text in the "Captured Data" area.

### Configuration Dump

Click **Dump Config** to read and display the current OSA configuration for the selected stack. The raw configuration output appears in the display area.

---

## 18. Common UI Patterns & Tips

### Confirmation Dialogs

All destructive or dangerous operations in Athena require confirmation before execution. The confirmation dialog pattern:

1. A modal dialog appears with a title describing the action.
2. A message explains the consequences.
3. Two buttons: **Cancel** (gray, flat) and a **Confirm** button.
4. For dangerous operations (CSR writes, error injection, bind/unbind, port control), the confirm button is rendered in **red** (`#ef5350`).
5. For less dangerous operations (partition toggle, clear events), the confirm button matches the action color (yellow for toggle, red for clear).

You must click the confirm button to proceed. Clicking Cancel or clicking outside the dialog dismisses it without action.

### Loading States

Buttons that trigger asynchronous operations show a **loading spinner** while the operation is in progress. During this time:
- The button is visually disabled.
- You cannot trigger the same operation again.
- The spinner automatically clears when the operation completes (success or failure).

### Notifications

Toast notifications appear at the top of the screen for operation results:
- **Green (positive):** Success messages (e.g., "Connected to PSX 48xG4").
- **Red (negative):** Error messages (e.g., "Connection failed: Device not found").
- **Yellow (warning):** Caution messages (e.g., "Injected DLLP CRC on port 0").
- **Blue (info):** Informational messages (e.g., "Disconnected", "Loopback disabled").

Notifications auto-dismiss after a few seconds.

### Live Monitoring

Several pages offer live monitoring with periodic polling:

| Page | Feature | Update Mechanism |
|---|---|---|
| Performance | Bandwidth chart | Timer-based polling (1s/2s/5s) |
| BER Testing | Error count chart | Timer-based polling (0.5s-10s) |
| Equalization | Cross-hair margin | 1s polling until measurement completes |

During live monitoring:
- Input controls are locked to prevent mid-stream changes.
- Charts update in place without page reloads (Plotly `update_figure`).
- Data is retained in memory up to a maximum number of points (typically 120).
- Stopping monitoring re-enables the input controls.

### Data Export

The Eye Diagram page supports data export:
- **CSV export:** Generates a file `eye_lane[N].csv` with columns `x,y,value`.
- **JSON export:** Generates a file `eye_lane[N].json` with structured metadata (lane_id, ranges, pixel counts, pixel array).

Both exports trigger a browser download.

### Color Coding Conventions Recap

| Context | Green | Yellow | Red |
|---|---|---|---|
| Link status | UP | Training | DOWN |
| Temperature | < 70 C | 70-84 C | >= 85 C |
| Event count | 0 events | 1-9 events | 10+ events |
| Confirmation buttons | Standard confirm | Warning action | Dangerous action |
| Step status | PASS | WARN | FAIL |

### Keyboard and Browser Tips

- **Browser back/forward:** Navigation works normally since each page has its own URL route.
- **Multiple tabs:** All tabs share the same device connection. Actions in one tab affect the device state visible in other tabs.
- **Page refresh:** Refreshing a page re-renders it from the current device state. Live monitoring timers are not preserved across page refreshes.
- **Bookmark pages:** You can bookmark specific pages (e.g., `http://localhost:8080/eye`) for quick access.

---

## 19. Troubleshooting

### Device Not Found During Scan

**Symptom:** Clicking "Scan" shows "No Switchtec devices found on this system."

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| No Switchtec device installed | Verify the PCIe card is physically seated and recognized by the OS |
| Driver not loaded | On Linux, ensure the `switchtec` kernel module is loaded (`lsmod \| grep switchtec`). On Windows, check Device Manager. |
| Permission denied | On Linux, you may need root access or udev rules for `/dev/switchtec*`. Run `athena serve` with `sudo` or configure appropriate permissions. |
| Wrong device path | Verify the device path exists (e.g., `ls /dev/switchtec*` on Linux) |

### Connection Failures

**Symptom:** Clicking "Connect" shows "Connection failed: [error message]."

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Invalid device path | Double-check the path. Ensure no extra spaces. Maximum 256 characters. |
| Device in use | Another process may have the device open. Close other Switchtec tools. |
| Device communication error | The device may be in a bad state. Try power-cycling the host or resetting the switch. |
| Stale connection | If a previous connection was not cleanly closed, the cached state may be stale. Restart `athena serve`. |

### "No Device Connected" Guard

**Symptom:** Navigating to any page shows the "No Device Connected" card.

**Solution:** Navigate to the Discovery page (`/`) and connect to a device first. All pages except Discovery require an active device connection.

### Chart Not Updating

**Symptom:** A live chart (bandwidth, BER) appears frozen or empty.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Monitoring not started | Click "Start Monitoring" to begin polling |
| No ports selected | Select at least one port in the multi-select |
| Device disconnected during monitoring | The timer may stop silently. Reconnect and restart monitoring. |
| Browser tab inactive | Some browsers throttle background tabs. Keep the tab focused. |
| WebSocket disconnected | Check the browser developer console for WebSocket errors. Refresh the page. |

### Firmware Operations Failing

**Symptom:** Toggle Active Partition or Toggle Boot RO fails with an error.

**Possible causes:**

| Cause | Solution |
|---|---|
| Device in BL2 boot phase | Some firmware operations are restricted during BL2. Wait for main firmware boot. |
| Read-only protection | Disable boot RO before attempting partition changes. |
| Communication timeout | The operation may take longer than expected. Try again. |

### Eye Diagram Capture Timeout

**Symptom:** Eye capture shows "Capture timed out" after 60 seconds.

**Possible causes:**

| Cause | Solution |
|---|---|
| Very large capture range | Reduce the range or increase step sizes |
| Link is down | Verify the port is linked UP before capturing |
| Hardware busy | The diagnostic engine may be occupied. Cancel and retry. |

### Browser Compatibility

Athena requires a modern web browser with **WebSocket support**. Tested browsers:

| Browser | Supported |
|---|---|
| Google Chrome 90+ | Yes |
| Mozilla Firefox 90+ | Yes |
| Microsoft Edge 90+ | Yes |
| Safari 14+ | Yes |
| Internet Explorer | No |

If you experience rendering issues, ensure your browser is up to date and that JavaScript and WebSockets are not blocked by network policies or browser extensions.

### MRPC Timeout / Communication Stall

**Symptom:** Operations hang and then fail with `SwitchtecTimeoutError` or `MrpcError: No available MRPC thread`.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Firmware boot still in progress | Wait for the switch to complete boot (check boot phase on Dashboard — should be `MAIN_FW`, not `BL2`). MRPC commands are unavailable during early boot. |
| Bad firmware state | The switch firmware may be in a degraded state (error code `0x64007`). Try a hard reset from the Dashboard or `athena device hard-reset <path>`. If persistent, power-cycle the host. |
| Diagnostic engine busy | Eye diagram capture, LTSSM logging, and pattern generation share the diagnostic engine. Cancel any running capture before starting a new operation. |
| No available MRPC thread | The switch has a limited number of MRPC threads. If multiple tools or processes are sending commands simultaneously, threads can be exhausted. Close other Switchtec tools (vendor GUI, other Athena instances). |
| PCIe link in recovery | If the link is continuously entering recovery, MRPC commands may be delayed. Check the LTSSM Trace page for rapid state transitions. |

**Debug steps:**

1. Run `athena device info <path>` from the CLI to check basic device responsiveness.
2. Check the server terminal for the full error code (e.g., `MRPC error 0x64001`).
3. If the device is unresponsive, try `athena device hard-reset <path>`.
4. As a last resort, power-cycle the host machine.

### Link Not Training

**Symptom:** Port shows `LINK DOWN` on the Ports page, or the LTSSM state is stuck in `Detect`, `Polling`, or `Compliance`.

**Debug procedure:**

1. **Check physical connectivity.** Verify the PCIe cable or card is firmly seated. For cabled connections (Serial Cables host cards), check both ends.

2. **Check LTSSM state.** Navigate to the LTSSM Trace page and read the log for the affected port.
   - **Stuck in Detect.Quiet:** No electrical presence detected. Check physical connection, slot power, and that the endpoint is powered.
   - **Stuck in Detect.Active:** Receiver detection is finding something but cannot proceed. Check for impedance mismatches or damaged connectors.
   - **Cycling Polling → Detect:** TS1/TS2 ordered sets are not being received correctly. Check signal integrity — may need retimers or shorter cables.
   - **Stuck in Polling.Compliance:** The link partner is not responding to TS1/TS2. Verify the endpoint firmware supports the configured link speed.
   - **Cycling Config → Recovery → Config:** Equalization is failing. Check TX EQ coefficients on the Equalization page. Try reducing the target link speed.

3. **Check the OSA page.** Use the Ordered Set Analyzer to capture TS1/TS2 during link training to verify ordered set content, lane numbers, and link/speed negotiation fields.

4. **Run the Link Training Debug recipe.** Navigate to the Workflows page and run "Link Training Debug" which automates LTSSM log capture, transition counting, and result analysis.

5. **Check the Eye Diagram.** If the link trains at a lower speed or width than expected, capture an eye diagram at the current speed to assess signal quality. Look for eye closure (height < 20mV or width < 0.15 UI indicates margin problems).

### Error Injection Not Working

**Symptom:** Error injection commands succeed but no errors appear on the link partner, or link does not go through recovery.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Wrong port selected | Error injection targets the specified physical port. Verify you are injecting on the correct port (check Ports page for port mapping). |
| Rate-based injector still disabled | DLLP CRC and TLP LCRC injectors must be explicitly enabled. Use the Error Injection page enable toggle, not just the inject button. |
| Link partner has error forwarding disabled | The link partner's AER capability may not be configured to detect the injected error type. This is a link-partner-side configuration issue. |
| Injection rate limit reached | Athena limits error injection to 10 per 60 seconds to prevent hardware damage. Wait for the rate limiter to reset, or use the CLI for higher-frequency testing. |
| Link is down | Error injection requires an active link. Verify the port is `LINK UP` before injecting. |

### Pattern Generator / BER Test Issues

**Symptom:** Pattern generator shows zero errors even with a known-bad link, or BER measurements are unexpectedly high.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Loopback not enabled | BER testing requires loopback mode. Verify loopback is enabled on the BER Testing page before starting pattern gen/mon. |
| Wrong generation selected | Pattern IDs differ between Gen4, Gen5, and Gen6. Verify the generation matches the current link speed. Athena's generation-specific pattern maps handle this automatically, but manual API calls must use the correct IDs. |
| Pattern monitor not started | The monitor must be configured and started after the generator. On the BER Testing page, configure the generator first, then start the monitor. |
| Lane mismatch | Pattern gen/mon operates per-lane. Ensure you are monitoring the same lanes where the generator is active. |
| Pattern monitor disabled (error `0x70b02`) | The pattern monitor was not enabled before reading. Enable it via the BER Testing page before reading results. |

### Firmware Write Failures

**Symptom:** Firmware write operation fails partway through or produces a verification error.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| Boot RO is enabled | Disable boot read-only protection before writing. Use the Firmware page to toggle Boot RO off. |
| Wrong partition selected | Verify you are writing to the inactive partition. Writing to the active partition while running from it will fail. |
| Image file too large or incompatible | Verify the firmware image matches the switch model (PSX/PFX/PAX) and partition type (IMG0/IMG1/CFG0/CFG1). |
| Communication interrupted | Firmware write is a long-running operation. Do not close the browser tab, disconnect the device, or stop the server during a write. |
| Device in BL2 phase | Full firmware operations require the main firmware to be running. If stuck in BL2, the device may need recovery-mode firmware programming via JTAG or I2C. |

### Performance Monitoring Shows Zero Bandwidth

**Symptom:** Bandwidth charts on the Performance page show flat zero even with active traffic.

**Possible causes and solutions:**

| Cause | Solution |
|---|---|
| No traffic flowing | Bandwidth counters measure actual PCIe TLP traffic. Verify the endpoint is generating traffic (e.g., DMA transfers, NVMe I/O). |
| Wrong port pair selected | Bandwidth is measured between an ingress and egress port pair. Verify the selected ports match the traffic path through the switch. |
| Counters not started | Click "Start Monitoring" on the Performance page to begin counter polling. |
| Polling interval too fast | Very short poll intervals may show zero if the counter delta is below the measurement resolution. Try a 1-second interval. |

### Remote Access / CORS Errors

**Symptom:** Browser shows CORS errors when accessing the dashboard from a remote machine.

**Solution:** Configure allowed CORS origins when starting the server:

```bash
# Allow access from a specific lab machine
athena serve --host 0.0.0.0 --cors-origins "http://10.0.0.50:8000"

# Allow all origins (open lab networks only)
athena serve --host 0.0.0.0 --cors-origins "*"

# Or via environment variable
export ATHENA_CORS_ORIGINS="http://labpc.corp:8000,http://10.0.0.50:8000"
athena serve --host 0.0.0.0
```

See the [Configuration Guide](setup/configuration.md) for details.

### General Diagnostics

If you encounter unexpected behavior:

1. **Check the terminal** where `athena serve` is running for error messages and stack traces.
2. **Check the browser console** (F12 > Console tab) for JavaScript errors or WebSocket disconnection messages.
3. **Refresh the page** to re-establish the WebSocket connection and re-render from current state.
4. **Restart the server** (`Ctrl+C` then `athena serve` again) to reset all state.
5. **Verify device access** independently using the `switchtec` CLI tools to confirm the device is responsive.
6. **Enable debug logging** with `athena --debug serve` to get verbose output including MRPC command/response tracing.

### Common Error Codes Quick Reference

| Error | Exception | Meaning | First Thing to Try |
|---|---|---|---|
| `errno 19 (ENODEV)` | `DeviceNotFoundError` | Device not present | Check physical connection, `ls /dev/switchtec*` |
| `errno 13 (EACCES)` | `SwitchtecPermissionError` | Permission denied | Add udev rule or run with `sudo` |
| `errno 110 (ETIMEDOUT)` | `SwitchtecTimeoutError` | Operation timed out | Reduce capture range, check link state |
| `MRPC 0x64001` | `MrpcError` | No MRPC thread available | Close other Switchtec tools, wait and retry |
| `MRPC 0x64007` | `MrpcError` | Bad firmware state | Hard reset or power-cycle |
| `MRPC 0x64010` | `SwitchtecPermissionError` | MRPC command denied | Check firmware permissions, update firmware |
| `MRPC 0x0000004a` | `UnsupportedError` | Feature not supported | Verify firmware version supports this feature |
| `MRPC 0x70b02` | `MrpcError` | Pattern monitor disabled | Enable pattern monitor before reading |
| `General 0x20000004` | `InvalidPortError` | Invalid port number | Verify port exists on this switch variant |
| `General 0x20000005` | `InvalidLaneError` | Invalid lane number | Check negotiated link width for valid lane range |

---

*This manual covers Athena dashboard version 1.0. For CLI usage, API reference, and architecture documentation, see the companion documents in the `docs/` directory.*
