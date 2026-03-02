# Workflow Recipes -- Architecture Design

**Status:** Implemented (18 recipes + Workflow Builder)
**Date:** 2026-03-01
**Last updated:** 2026-03-01 (Workflow Builder implemented, PCIe validation engineer review feedback incorporated)
**Context:** PCIe validation engineer review identified that UI users need one-click access to common validation workflows, not raw CLI-level control. This is especially important for demos and monitoring-focused users.

---

## Problem

The core domain layer exposes 10+ managers with 60+ individual methods. CLI and API users compose these into workflows via scripts. UI users need pre-composed "recipes" that:
- Require minimal input (select a port, click Run)
- Show live progress as steps execute
- Display pass/fail results with detail
- Work well for demos and quick validation checks

## Design Principles

1. **Recipes live in the core layer** -- not in the UI. Testable with FakeLibrary, reusable from CLI/API/UI.
2. **Generator-based streaming** -- each recipe is a generator yielding `RecipeResult` objects. The UI renders each result as it arrives (live stepper). The CLI can print them. The API can stream them via WebSocket.
3. **Port-centric input** -- most recipes take a device + port ID. Some take additional parameters (lane, duration, error type). Keep inputs minimal.
4. **Immutable results** -- `RecipeResult` is a frozen Pydantic model, consistent with the rest of the codebase.
5. **No new dependencies** -- recipes compose existing manager calls. No new C bindings needed.

---

## Recipe Categories

Recipes are grouped into categories for UI navigation and filtering:

| Category | Description | Recipes |
|----------|-------------|---------|
| **Link Health** | Port status, LTSSM, temperature, counters | All-Port Status Sweep, Link Health Check, Link Training Debug, LTSSM State Monitor |
| **Signal Integrity** | Eye diagrams, margins, equalization | Eye Diagram Quick Scan, Cross-Hair Margin Analysis, Port EQ Report |
| **Error Testing** | BER, injection, recovery | BER Soak Test, Loopback BER Sweep, Error Injection + Recovery |
| **Performance** | Bandwidth, latency, baselines | Bandwidth Baseline, Latency Measurement Profile, Event Counter Stress Baseline |
| **Configuration** | Config space, firmware, fabric | Config Space Dump, Firmware Validation, Fabric Bind/Unbind Validation |
| **Debug** | OSA captures, thermal profiling | OSA Link Training Capture, Switch Thermal Profile |

---

## Data Model

```python
# src/serialcables_switchtec/core/workflows/models.py

from enum import IntEnum
from pydantic import BaseModel, ConfigDict

class RecipeCategory(str, Enum):
    """Category for UI grouping and filtering."""
    LINK_HEALTH = "link_health"
    SIGNAL_INTEGRITY = "signal_integrity"
    ERROR_TESTING = "error_testing"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"
    DEBUG = "debug"

class StepStatus(IntEnum):
    """Outcome of a single recipe step."""
    RUNNING = 0
    PASS = 1
    FAIL = 2
    WARN = 3
    INFO = 4
    SKIP = 5

class StepCriticality(str, Enum):
    """Whether a step failure should abort the recipe."""
    CRITICAL = "critical"      # Failure aborts remaining steps
    NON_CRITICAL = "non_critical"  # Failure logged, recipe continues

class RecipeResult(BaseModel):
    """A single step result yielded by a recipe generator."""
    model_config = ConfigDict(frozen=True)

    recipe_name: str          # "link_health_check"
    step: str                 # Human-readable step name: "Checking LTSSM state"
    step_index: int           # 0-based step number
    total_steps: int          # Total steps in this recipe
    status: StepStatus        # PASS, FAIL, WARN, INFO
    criticality: StepCriticality = StepCriticality.NON_CRITICAL
    detail: str               # "Port 0: L0 (link up, x4 Gen4)"
    data: dict | None = None  # Optional structured data for UI rendering

class RecipeSummary(BaseModel):
    """Final summary after all steps complete."""
    model_config = ConfigDict(frozen=True)

    recipe_name: str
    total_steps: int
    passed: int
    failed: int
    warnings: int
    skipped: int
    aborted: bool             # True if a CRITICAL step failed
    elapsed_s: float
    results: list[RecipeResult]
```

### Typed Data Models

Each recipe defines its own typed data model for `RecipeResult.data` instead of raw dicts.
This enables type-safe UI rendering and serialization:

```python
# Example: link health step data
class PortStatusData(BaseModel):
    model_config = ConfigDict(frozen=True)
    link_up: bool
    neg_width: int            # x1, x2, x4, x8, x16
    neg_rate: str             # "Gen4", "Gen5", "Gen6"
    ltssm_state: str          # "L0", "Detect.Quiet", etc.
    max_width: int

class TempData(BaseModel):
    model_config = ConfigDict(frozen=True)
    die_temps: list[float]    # Per-die temperatures in Celsius
    threshold_c: float        # Warning threshold

# RecipeResult.data stores the .model_dump() of these typed models.
# The UI can reconstruct the typed model via ModelClass.model_validate(result.data).
```

---

## Recipe Interface

```python
# src/serialcables_switchtec/core/workflows/base.py

import threading
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

class Recipe(ABC):
    """Base class for all workflow recipes."""

    name: str                     # Machine-readable name
    display_name: str             # Human-readable name for UI
    description: str              # One-line description
    category: RecipeCategory      # UI grouping category

    @abstractmethod
    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        """Execute the recipe, yielding step results.

        The generator yields RecipeResult for each step as it completes.
        The final return value is a RecipeSummary.

        Implementations MUST check ``cancel.is_set()`` before each step
        and between loop iterations. When cancelled, yield a SKIP result
        for remaining steps and return the summary.

        Args:
            dev: Open device handle.
            cancel: Threading event for graceful cancellation.
            **kwargs: Recipe-specific parameters (port_id, lane_id, etc.)
        """
        ...

    @abstractmethod
    def parameters(self) -> list[RecipeParameter]:
        """Describe the parameters this recipe accepts.

        Used by the UI to render input controls (dropdowns, sliders, etc.)
        """
        ...

    @abstractmethod
    def estimated_duration_s(self, **kwargs) -> float:
        """Approximate runtime in seconds given the input parameters.

        Some recipes have fixed duration (e.g., Link Health Check ~2s).
        Others depend on inputs (e.g., BER Soak = duration_s parameter).
        """
        ...
```

```python
# Parameter descriptor for UI rendering
class RecipeParameter(BaseModel):
    """Describes a recipe input parameter for UI auto-generation."""
    model_config = ConfigDict(frozen=True)

    name: str                     # "port_id"
    display_name: str             # "Port"
    param_type: str               # "port_select" | "lane_select" | "int" | "float" | "choice" | "duration"
    required: bool = True
    default: int | float | str | None = None
    choices: list[str] | None = None  # For "choice" type
    min_val: int | float | None = None
    max_val: int | float | None = None
    depends_on: str | None = None  # Parameter dependency (e.g., lane_select depends on port_select)
```

---

## Planned Recipes (18 total)

### Category: Link Health

#### 1. All-Port Status Sweep *(Priority #1)*
- **Category:** Link Health
- **Input:** *(none -- scans all ports)*
- **Duration:** ~3s
- **Steps:**
  1. Enumerate all ports on the switch
  2. For each port: read link status (up/down, width, rate, LTSSM state)
  3. Flag any port with link down, width degradation, or unexpected LTSSM state
  4. Read die temperatures (warn if any >85C)
  5. Summary: port map with color-coded status (green/yellow/red)
- **Use case:** First thing to run after power-on or cable change. One-click overview of the entire switch.
- **UI rendering:** Port grid/matrix with status badges. The "home screen" recipe.
- **Step criticality:** Step 1 is CRITICAL (no ports = abort). Steps 2-4 are NON_CRITICAL.

#### 2. Link Health Check
- **Category:** Link Health
- **Input:** port_id
- **Duration:** ~2s
- **Steps:**
  1. Read port status (link up/down, negotiated width, rate) *(CRITICAL)*
  2. Check LTSSM state (expect L0 for active link)
  3. Check for width degradation (negotiated vs max capable)
  4. Read die temperature (warn if >85C)
  5. Read event counters (warn if non-zero error counts)
  6. Read bandwidth counters (info: current utilization)
  7. Read LTSSM log for recent transitions (info: last N state changes)
- **Use case:** Quick sanity check on a specific port after cable change or power cycle

#### 3. Link Training Debug
- **Category:** Link Health
- **Input:** port_id
- **Duration:** ~5s
- **Steps:**
  1. Clear LTSSM log
  2. Read current LTSSM state and link status
  3. If link is down: capture current LTSSM state for debug
  4. Read EQ status (did equalization complete? which phases?)
  5. Read TX coefficients (local and far end) to check convergence
  6. Read FS/LF values
  7. Read LTSSM log (full transition history since clear)
  8. Summary: training status with root cause hints (e.g., "stuck in Polling.Compliance")
- **Use case:** Debug link training failures. Run this when a port won't link up.
- **UI rendering:** LTSSM state timeline + EQ convergence table

#### 4. LTSSM State Monitor
- **Category:** Link Health
- **Input:** port_id, duration_s (default 30), poll_interval_s (default 0.5)
- **Duration:** User-defined (30s default)
- **Steps:**
  1. Read initial LTSSM state *(CRITICAL -- must be reachable)*
  2. Loop: poll LTSSM state at interval, yield on state change
  3. Detect transitions (L0 -> Recovery, Recovery -> L0, etc.)
  4. Summary: transition count, time-in-state breakdown, unexpected transitions
- **Use case:** Catch intermittent link retraining events. Run during stress testing.
- **UI rendering:** Live LTSSM state indicator with transition log

### Category: Signal Integrity

#### 5. Eye Diagram Quick Scan
- **Category:** Signal Integrity
- **Input:** port_id, lane_id (default 0; depends_on port_id)
- **Duration:** ~30s (hardware-dependent)
- **Steps:**
  1. Verify port is linked up *(CRITICAL)*
  2. Start eye capture with sensible defaults (x_step=1, y_step=2)
  3. Poll eye fetch until complete (yield progress updates with % complete)
  4. Compute eye opening metrics (height, width) from raw data
  5. Return eye data for chart rendering
  6. Cancel capture (cleanup)
- **Use case:** Quick signal quality assessment
- **UI rendering:** Eye diagram chart (already scaffolded in ui/components/eye_chart.py)

#### 6. Cross-Hair Margin Analysis
- **Category:** Signal Integrity
- **Input:** port_id, lane_id (default 0; depends_on port_id)
- **Duration:** ~10s per lane
- **Steps:**
  1. Verify port is linked up *(CRITICAL)*
  2. Enable cross-hair mode
  3. Sweep horizontal: find left/right eye boundaries
  4. Sweep vertical: find top/bottom eye boundaries
  5. Disable cross-hair mode (cleanup)
  6. Summary: margin values (mUI horizontal, mV vertical) with pass/fail thresholds
- **Use case:** Quantitative margin measurement. More precise than eye scan for compliance.
- **UI rendering:** Margin bar chart (horizontal and vertical) with spec limits overlay

#### 7. Port Equalization Report
- **Category:** Signal Integrity
- **Input:** port_id, link (current/previous, default current)
- **Duration:** ~3s
- **Steps:**
  1. Read TX coefficients per lane (local end)
  2. Read TX coefficients per lane (far end)
  3. Read EQ table with FOM values per lane
  4. Read FS/LF values
  5. Read receiver calibration (CTLE, DFE taps) per lane
  6. Summary: per-lane coefficient breakdown with convergence assessment
- **Use case:** Full equalization snapshot for debug or documentation
- **UI rendering:** Table view with coefficient values per lane, FOM heatmap

### Category: Error Testing

#### 8. BER Soak Test
- **Category:** Error Testing
- **Input:** port_id, pattern (default prbs31), duration_s (default 60), gen (default gen4)
- **Duration:** User-defined (60s default)
- **Steps:**
  1. Verify port is linked up *(CRITICAL)*
  2. Record initial link state (width, rate)
  3. Configure pattern generator with gen-specific pattern map
  4. Loop: read pattern monitor at 1s intervals, yield error count delta
  5. Check for link retraining events during soak (read LTSSM log)
  6. Stop pattern generator (cleanup)
  7. Summary: total errors, error rate, pass/fail threshold (1e-12 typical)
- **Use case:** Bit error rate validation for signal integrity
- **UI rendering:** Live error count chart with running BER calculation

#### 9. Loopback BER Sweep
- **Category:** Error Testing
- **Input:** port_id, gen (default gen4), patterns (default all-for-gen), duration_per_pattern_s (default 10)
- **Duration:** num_patterns * duration_per_pattern_s
- **Steps:**
  1. Verify port is linked up *(CRITICAL)*
  2. Enable loopback mode
  3. For each pattern in the gen-specific map:
     a. Configure pattern generator
     b. Soak for duration_per_pattern_s, yield periodic error deltas
     c. Record final BER for this pattern
  4. Disable loopback mode (cleanup)
  5. Summary: per-pattern BER table, worst-case pattern identified
- **Use case:** Comprehensive pattern sweep to find weakest PRBS pattern. Standard SI validation.
- **UI rendering:** Per-pattern BER bar chart, pattern comparison table

#### 10. Error Injection + Recovery
- **Category:** Error Testing
- **Input:** port_id, error_type (choice: dllp-crc, tlp-lcrc, seq-num, ack-nack, cto)
- **Duration:** ~5s
- **Steps:**
  1. Read initial LTSSM state (expect L0) *(CRITICAL)*
  2. Read initial event counters (baseline)
  3. Read initial AER status (baseline)
  4. Inject the selected error
  5. Wait 500ms
  6. Re-read LTSSM state (verify still L0 or recovered to L0)
  7. Re-read event counters (verify error was counted, report delta)
  8. Re-read AER status (verify AER bit set if applicable)
  9. Summary: injected, detected, recovered, AER reported (pass/fail per check)
- **Use case:** Verify error detection and recovery paths work
- **UI rendering:** Before/after comparison table with pass/fail badges

### Category: Performance

#### 11. Bandwidth Baseline
- **Category:** Performance
- **Input:** port_ids (multi-select), sample_count (default 10), interval_s (default 1.0)
- **Duration:** sample_count * interval_s
- **Steps:**
  1. Initial clear read (baseline)
  2. Loop: sample bandwidth, yield per-port egress/ingress totals with breakdown (posted/comp/nonposted)
  3. Summary: average, peak, min for each port. Flag asymmetric traffic.
- **Use case:** Establish performance baseline, detect bottlenecks
- **UI rendering:** Live bandwidth chart (already scaffolded in ui/pages/performance.py)

#### 12. Latency Measurement Profile
- **Category:** Performance
- **Input:** port_id, sample_count (default 100), egress_port_id (optional)
- **Duration:** ~5s
- **Steps:**
  1. Verify port is linked up *(CRITICAL)*
  2. Configure latency measurement (ingress port → egress port)
  3. Loop: collect latency samples, yield percentile updates
  4. Summary: min, avg, p50, p95, p99, max latency in nanoseconds
- **Use case:** Measure switch traversal latency for performance-sensitive workloads
- **UI rendering:** Latency histogram + percentile table

#### 13. Event Counter Stress Baseline
- **Category:** Performance
- **Input:** port_id, counter_types (multi-select, default all available), duration_s (default 30)
- **Duration:** User-defined (30s default)
- **Steps:**
  1. Enumerate available event counter types for the port
  2. Configure counters for selected types
  3. Initial clear read (baseline)
  4. Loop: sample all configured counters at 1s intervals, yield deltas
  5. Summary: per-counter totals, rates, any non-zero error counters flagged
- **Use case:** Establish error counter baseline under idle or load conditions
- **UI rendering:** Counter table with delta sparklines

### Category: Configuration

#### 14. Config Space Dump
- **Category:** Configuration
- **Input:** pdfid
- **Duration:** ~2s
- **Steps:**
  1. Read PCI header (vendor/device ID, command, status)
  2. Walk capability list (offset 0x34 pointer chain)
  3. Identify PCIe capability, AER capability offsets
  4. Read key registers (Link Control, Link Status, Device Control, Device Status)
  5. Read AER registers (uncorrectable/correctable status, mask, severity)
  6. Summary: formatted config space dump with field decode
- **Use case:** Quick endpoint identification and status check
- **UI rendering:** Formatted register table with bit-field decode

#### 15. Firmware Validation
- **Category:** Configuration
- **Input:** *(none -- reads device state)*
- **Duration:** ~2s
- **Steps:**
  1. Read firmware version string
  2. Read firmware partition summary (active/inactive, versions, CRC)
  3. Check boot phase (expect FW, warn if BL2)
  4. Check boot RO status
  5. Compare active vs inactive partition versions
  6. Summary: firmware state report with upgrade recommendation if mismatched
- **Use case:** Pre-flight firmware check. Verify expected version is running.
- **UI rendering:** Firmware status card with partition table

#### 16. Fabric Bind/Unbind Validation
- **Category:** Configuration
- **Input:** port_id, ep_pdfid
- **Duration:** ~5s
- **Steps:**
  1. Read current port config (baseline) *(CRITICAL)*
  2. Read current GFMS events (baseline)
  3. Perform bind operation
  4. Verify bind succeeded (re-read port config, check bound state)
  5. Read GFMS events (verify bind event recorded)
  6. Perform unbind operation
  7. Verify unbind succeeded (re-read port config, check unbound state)
  8. Summary: bind/unbind round-trip pass/fail
- **Use case:** Validate fabric operations on CXL/fabric-enabled switches
- **UI rendering:** State transition diagram (unbound → bound → unbound) with pass/fail

### Category: Debug

#### 17. OSA Link Training Capture
- **Category:** Debug
- **Input:** port_id, capture_type (choice: ltssm, ordered-set), trigger (choice: on-retrain, manual)
- **Duration:** ~10s (depends on trigger)
- **Steps:**
  1. Configure OSA capture type and pattern
  2. Arm capture trigger
  3. If manual trigger: initiate link retrain
  4. Poll capture status until complete (yield progress)
  5. Read captured data
  6. Summary: captured ordered sets / LTSSM transitions with timestamps
- **Use case:** Deep debug of link training or retrain events at ordered-set level
- **UI rendering:** Ordered-set timeline / LTSSM waveform view

#### 18. Switch Thermal Profile
- **Category:** Debug
- **Input:** duration_s (default 60), interval_s (default 5.0)
- **Duration:** User-defined (60s default)
- **Steps:**
  1. Read initial die temperatures (all dies)
  2. Loop: sample temperatures at interval, yield per-die readings
  3. Summary: per-die min/avg/max, temperature trend (rising/stable/falling), thermal throttle risk
- **Use case:** Thermal characterization under load. Run alongside traffic generation.
- **UI rendering:** Multi-line temperature chart with threshold markers

---

## Module Structure

```
src/serialcables_switchtec/core/workflows/
|-- __init__.py              # Exports RECIPE_REGISTRY, get_recipe(), get_recipes_by_category()
|-- models.py                # RecipeResult, RecipeSummary, RecipeParameter, StepStatus, RecipeCategory
|-- base.py                  # Recipe ABC with cancel token
|-- data_models.py           # Typed data models for RecipeResult.data (PortStatusData, TempData, etc.)
|
|-- # Link Health
|-- all_port_sweep.py        # AllPortStatusSweepRecipe
|-- link_health.py           # LinkHealthCheckRecipe
|-- link_training_debug.py   # LinkTrainingDebugRecipe
|-- ltssm_monitor.py         # LtssmStateMonitorRecipe
|
|-- # Signal Integrity
|-- eye_scan.py              # EyeDiagramQuickScanRecipe
|-- crosshair_margin.py      # CrossHairMarginAnalysisRecipe
|-- eq_report.py             # PortEqualizationReportRecipe
|
|-- # Error Testing
|-- ber_soak.py              # BerSoakTestRecipe
|-- loopback_sweep.py        # LoopbackBerSweepRecipe
|-- inject_recover.py        # ErrorInjectionRecoveryRecipe
|
|-- # Performance
|-- bandwidth.py             # BandwidthBaselineRecipe
|-- latency_profile.py       # LatencyMeasurementProfileRecipe
|-- evcntr_baseline.py       # EventCounterStressBaselineRecipe
|
|-- # Configuration
|-- config_dump.py           # ConfigSpaceDumpRecipe
|-- firmware_validate.py     # FirmwareValidationRecipe
|-- fabric_validate.py       # FabricBindUnbindValidationRecipe
|
|-- # Debug
|-- osa_capture.py           # OsaLinkTrainingCaptureRecipe
+-- thermal_profile.py       # SwitchThermalProfileRecipe
```

### Registry Pattern

```python
# src/serialcables_switchtec/core/workflows/__init__.py

from serialcables_switchtec.core.workflows.all_port_sweep import AllPortStatusSweepRecipe
from serialcables_switchtec.core.workflows.link_health import LinkHealthCheckRecipe
# ... etc (all 18 imports)

RECIPE_REGISTRY: dict[str, type[Recipe]] = {
    # Link Health
    "all_port_status_sweep": AllPortStatusSweepRecipe,
    "link_health_check": LinkHealthCheckRecipe,
    "link_training_debug": LinkTrainingDebugRecipe,
    "ltssm_state_monitor": LtssmStateMonitorRecipe,
    # Signal Integrity
    "eye_diagram_quick_scan": EyeDiagramQuickScanRecipe,
    "crosshair_margin_analysis": CrossHairMarginAnalysisRecipe,
    "port_eq_report": PortEqualizationReportRecipe,
    # Error Testing
    "ber_soak_test": BerSoakTestRecipe,
    "loopback_ber_sweep": LoopbackBerSweepRecipe,
    "error_injection_recovery": ErrorInjectionRecoveryRecipe,
    # Performance
    "bandwidth_baseline": BandwidthBaselineRecipe,
    "latency_measurement_profile": LatencyMeasurementProfileRecipe,
    "event_counter_stress_baseline": EventCounterStressBaselineRecipe,
    # Configuration
    "config_space_dump": ConfigSpaceDumpRecipe,
    "firmware_validation": FirmwareValidationRecipe,
    "fabric_bind_unbind_validation": FabricBindUnbindValidationRecipe,
    # Debug
    "osa_link_training_capture": OsaLinkTrainingCaptureRecipe,
    "switch_thermal_profile": SwitchThermalProfileRecipe,
}

def get_recipe(name: str) -> type[Recipe]:
    """Look up a recipe by name."""
    if name not in RECIPE_REGISTRY:
        raise KeyError(f"Unknown recipe: {name}. Available: {list(RECIPE_REGISTRY)}")
    return RECIPE_REGISTRY[name]

def get_recipes_by_category(category: RecipeCategory) -> dict[str, type[Recipe]]:
    """Return all recipes in a given category."""
    return {
        name: cls for name, cls in RECIPE_REGISTRY.items()
        if cls.category == category
    }
```

---

## Integration Points

### UI (NiceGUI Dashboard)

```
ui/pages/workflows.py     # Workflow launcher page
ui/components/
|-- recipe_card.py         # Card with name, description, parameter inputs, Run button
|-- recipe_stepper.py      # Live progress stepper rendering RecipeResult stream
+-- recipe_summary.py      # Pass/fail summary badge
```

**Flow:**
1. Workflows page groups recipes by `RecipeCategory` with tab or sidebar navigation
2. User selects a recipe card → parameter inputs appear (auto-generated from `recipe.parameters()`, respecting `depends_on`)
3. User clicks Run → UI creates a `threading.Event` cancel token and calls `recipe.run(dev, cancel, **params)` in a background thread
4. Each yielded `RecipeResult` is pushed to the UI via NiceGUI's `ui.timer` or async update
5. Stepper shows: step name, status badge (green/red/yellow), detail text, criticality indicator
6. Cancel button sets the cancel event → recipe yields SKIP for remaining steps and cleans up
7. On completion, `RecipeSummary` is rendered as a header badge (e.g., "5/5 PASSED") and persisted to history

### CLI

```bash
# List available recipes
athena workflow list

# Run a recipe
athena workflow run link_health_check /dev/switchtec0 --port 0

# JSON output for scripting
athena --json-output workflow run ber_soak_test /dev/switchtec0 --port 0 --duration 60
```

### REST API

```
GET  /api/workflows/                              # List available recipes with parameters
POST /api/devices/{id}/workflows/{recipe_name}     # Start a recipe (returns job ID)
GET  /api/devices/{id}/workflows/jobs/{job_id}     # Poll job status + results
WS   /api/devices/{id}/workflows/{recipe_name}/ws  # WebSocket stream of RecipeResult
```

---

## Testing Strategy

Each recipe is testable with FakeLibrary since recipes compose existing manager methods:

```python
import threading
from serialcables_switchtec.testing import create_mock_device
from serialcables_switchtec.core.workflows import get_recipe
from serialcables_switchtec.core.workflows.models import StepStatus

def test_link_health_check_all_pass():
    result = create_mock_device()
    dev, fake_lib = result.device, result.fake_lib
    cancel = threading.Event()  # Not cancelled

    # Configure mocks for happy path
    fake_lib.switchtec_status.return_value = 0
    # ... configure other mocks

    recipe = get_recipe("link_health_check")()
    results = list(recipe.run(dev, cancel, port_id=0))

    assert all(r.status == StepStatus.PASS for r in results)

def test_link_health_check_link_down():
    # Configure mock for link-down port
    # Verify step 1 returns FAIL with appropriate detail (CRITICAL step aborts)
    ...

def test_recipe_cancellation():
    result = create_mock_device()
    dev, fake_lib = result.device, result.fake_lib
    cancel = threading.Event()
    cancel.set()  # Pre-cancelled

    recipe = get_recipe("link_health_check")()
    results = list(recipe.run(dev, cancel, port_id=0))

    # All steps should be SKIP when cancelled before start
    assert all(r.status == StepStatus.SKIP for r in results)
```

---

## Implementation Priority

When implementation begins (after UI is further along):

1. **Phase 1: Foundation + First Recipes** *(validates the pattern)*
   - Models, base class, cancellation infrastructure, persistence layer
   - All-Port Status Sweep *(priority #1 -- the "home screen" recipe)*
   - Link Health Check *(simplest single-port recipe)*
   - Firmware Validation *(no port required, good smoke test)*

2. **Phase 2: Monitoring Recipes** *(builds on existing watch generators)*
   - Bandwidth Baseline
   - Event Counter Stress Baseline
   - Switch Thermal Profile
   - LTSSM State Monitor

3. **Phase 3: Error Testing** *(composition of inject + monitor + verify)*
   - BER Soak Test
   - Error Injection + Recovery
   - Loopback BER Sweep

4. **Phase 4: Signal Integrity** *(depends on UI chart rendering being ready)*
   - Eye Diagram Quick Scan
   - Cross-Hair Margin Analysis
   - Port Equalization Report

5. **Phase 5: Configuration + Debug** *(read-heavy, table rendering + advanced features)*
   - Config Space Dump
   - Link Training Debug
   - Fabric Bind/Unbind Validation
   - OSA Link Training Capture
   - Latency Measurement Profile

Each phase is independently shippable. Phase 1 establishes the pattern; phases 2-5 are parallel-implementable after Phase 1 is validated.

---

## Resolved Design Decisions

These were open questions in the original architecture. Resolved per PCIe validation engineer review:

1. **Cancellation: MANDATORY.** Every recipe receives a `threading.Event` cancel token as a required parameter. Recipes MUST check `cancel.is_set()` before each step and between loop iterations. Long-running recipes (BER Soak, LTSSM Monitor, Thermal Profile) must be cancellable mid-soak. On cancel, yield SKIP for remaining steps, run cleanup (disable loopback, stop pattern gen, etc.), and return summary with `aborted=True`.

2. **Persistence: YES.** Recipe results are persisted for "last N runs" history in the dashboard. Implementation: JSON files in a configurable directory (`~/.athena/recipe_history/`). Each run produces a `{recipe_name}_{timestamp}.json` containing the `RecipeSummary`. A `RecipeHistoryManager` handles rotation (default: keep last 50 runs per recipe). Valuable for demos and regression tracking.

3. **Custom recipes:** Deferred — start with hardcoded recipes, add configurability if users request it.

4. **Parallel recipes:** One recipe per device at a time, enforced by the UI/API. The `device_op()` lock serializes C calls, so recipes are thread-safe, but concurrent recipes would interleave steps unpredictably.

5. **Error handling strategy:** Steps are tagged with `StepCriticality`. CRITICAL steps (e.g., "verify port is linked up") abort the recipe on failure. NON_CRITICAL steps (e.g., "read event counters") log the failure and continue. This prevents a non-essential read failure from aborting an otherwise useful recipe run.

6. **Typed data models:** `RecipeResult.data` stores `.model_dump()` of typed Pydantic models (e.g., `PortStatusData`, `TempData`, `BerSampleData`). The UI reconstructs the typed model via `ModelClass.model_validate(result.data)` for type-safe rendering. Defined in `data_models.py`.

7. **`estimated_duration_s` is a method**, not a class attribute. Some recipes have input-dependent duration (BER Soak = `duration_s` param, Loopback Sweep = `num_patterns * duration_per_pattern_s`). The method receives `**kwargs` matching the recipe's parameters.

8. **`depends_on` for parameters:** `RecipeParameter` includes an optional `depends_on` field. Example: `lane_id` depends on `port_id` — the UI disables/hides the lane selector until a port is selected, then populates lane choices based on the selected port's width.

---

## Workflow Builder (Recipe Chaining) -- Implemented

Open Question #3 ("Recipe chaining") is now resolved. The Workflow Builder allows users to compose recipes into multi-step sequences and run them as a single workflow.

### Architecture

```
core/workflows/
  workflow_models.py     # WorkflowStep, WorkflowDefinition, WorkflowStepSummary, WorkflowSummary (Pydantic, frozen)
  workflow_storage.py    # Save/load/list/delete JSON from ~/.switchtec/workflows/ (path-confined)
  workflow_executor.py   # Sequential runner with prefixed results, abort-on-critical, cancel propagation

ui/components/
  param_inputs.py            # Extracted shared param_input() + extract_value()
  workflow_step_editor.py    # Single step row editor component

ui/pages/
  workflow_builder.py    # Full builder page: metadata, step list, save/load/delete/run

cli/
  recipe.py              # list-workflows and run-workflow subcommands
```

### Key Design Decisions

- **Pydantic models with `frozen=True`** for immutability (consistent with RecipeResult, RecipeSummary)
- **Field names:** `recipe_key` (not `recipe_name`) to match RECIPE_REGISTRY keys
- **`abort_on_critical_fail`** only triggers on `StepCriticality.CRITICAL` failures, not all `StepStatus.FAIL`
- **Path confinement** in storage via `resolve().is_relative_to()` to prevent directory traversal
- **Up-front param validation** against recipe's declared `parameters()` before any step runs
- **Result prefixing:** `"[1/3] RecipeName > StepName"` so existing RecipeStepper renders workflow context without modification
- **Same thread+queue+timer pattern** as existing workflows.py page for UI execution
- **Shared `param_inputs.py`** extracted from recipe_card.py to share input generation between recipe card and workflow step editor

### Workflow Persistence

Workflows are saved as JSON in `~/.switchtec/workflows/` (one file per workflow, named by slug):

```json
{
  "name": "Morning Checkout",
  "description": "Daily port validation sequence",
  "steps": [
    {"recipe_key": "link_health_check", "label": "", "params": {"port_id": 0}},
    {"recipe_key": "thermal_profile", "label": "", "params": {"duration_s": 10}}
  ],
  "abort_on_critical_fail": true,
  "created_at": "2026-03-01T12:00:00+00:00",
  "updated_at": "2026-03-01T12:00:00+00:00"
}
```

### Executor Protocol

The `WorkflowExecutor` uses the same generator protocol as individual recipes:
- Yields `RecipeResult` objects (with prefixed step names) for each step of each recipe
- Returns `WorkflowSummary` via `StopIteration.value`
- Accepts a `threading.Event` cancel token, checked between recipes
- On exception: calls `recipe.cleanup()`, yields a FAIL result, optionally aborts

### Deferred Features (Tier 2+)

| Feature | Status | Notes |
|---------|--------|-------|
| Data flow mapping (A.data["temp"] -> B.kwargs["threshold"]) | Deferred | `depends_on` field on RecipeParameter exists but unused |
| Conditional skip/branch on step status | Deferred | Would need on_fail/on_warn fields on WorkflowStep |
| Parallel recipe execution (A and B concurrently, then C) | Deferred | Would need DAG model, not sequential list |
| Loops/retry with backoff | Deferred | |
| Drag-and-drop canvas UI | Deferred | Current UI uses list-based step editor |
| REST API CRUD endpoints for workflows | Deferred | CLI and UI only for now |

---

## Open Questions (resolve during implementation)

1. **History UI:** How should the dashboard present recipe history? Options: sidebar timeline, dedicated history page, or inline "last run" badge on each recipe card.

2. **Export format:** Should recipe results be exportable beyond JSON? CSV for BER data, PDF for reports? Defer until user feedback.
