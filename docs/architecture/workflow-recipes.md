# Workflow Recipes -- Architecture Design

**Status:** Architecture approved, implementation deferred until UI is further along
**Date:** 2026-03-01
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

## Data Model

```python
# src/serialcables_switchtec/core/workflows/models.py

from enum import IntEnum
from pydantic import BaseModel, ConfigDict

class StepStatus(IntEnum):
    """Outcome of a single recipe step."""
    RUNNING = 0
    PASS = 1
    FAIL = 2
    WARN = 3
    INFO = 4
    SKIP = 5

class RecipeResult(BaseModel):
    """A single step result yielded by a recipe generator."""
    model_config = ConfigDict(frozen=True)

    recipe_name: str          # "link_health_check"
    step: str                 # Human-readable step name: "Checking LTSSM state"
    step_index: int           # 0-based step number
    total_steps: int          # Total steps in this recipe
    status: StepStatus        # PASS, FAIL, WARN, INFO
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
    elapsed_s: float
    results: list[RecipeResult]
```

---

## Recipe Interface

```python
# src/serialcables_switchtec/core/workflows/base.py

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

class Recipe(ABC):
    """Base class for all workflow recipes."""

    name: str                  # Machine-readable name
    display_name: str          # Human-readable name for UI
    description: str           # One-line description
    estimated_duration_s: float  # Approximate runtime

    @abstractmethod
    def run(self, dev: SwitchtecDevice, **kwargs) -> Generator[RecipeResult, None, RecipeSummary]:
        """Execute the recipe, yielding step results.

        The generator yields RecipeResult for each step as it completes.
        The final return value is a RecipeSummary.

        Args:
            dev: Open device handle.
            **kwargs: Recipe-specific parameters (port_id, lane_id, etc.)
        """
        ...

    @abstractmethod
    def parameters(self) -> list[RecipeParameter]:
        """Describe the parameters this recipe accepts.

        Used by the UI to render input controls (dropdowns, sliders, etc.)
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
```

---

## Planned Recipes

### 1. Link Health Check
- **Input:** port_id
- **Duration:** ~2s
- **Steps:**
  1. Read port status (link up/down, negotiated width, rate)
  2. Check LTSSM state (expect L0 for active link)
  3. Read die temperature (warn if >85C)
  4. Read event counters (warn if non-zero error counts)
  5. Read bandwidth counters (info: current utilization)
- **Use case:** Quick sanity check after cable change or power cycle

### 2. Eye Diagram Quick Scan
- **Input:** port_id, lane_id (default 0)
- **Duration:** ~30s (hardware-dependent)
- **Steps:**
  1. Verify port is linked up
  2. Start eye capture with sensible defaults (x_step=1, y_step=2)
  3. Poll eye fetch until complete (yield progress updates)
  4. Return eye data for chart rendering
  5. Cancel capture (cleanup)
- **Use case:** Quick signal quality assessment
- **UI rendering:** Eye diagram chart (already scaffolded in ui/components/eye_chart.py)

### 3. BER Soak Test
- **Input:** port_id, pattern (default prbs31), duration_s (default 60), gen (default gen4)
- **Duration:** User-defined (60s default)
- **Steps:**
  1. Verify port is linked up
  2. Configure pattern generator
  3. Loop: read pattern monitor at 1s intervals, yield error count delta
  4. Stop pattern generator
  5. Summary: total errors, error rate, pass/fail threshold
- **Use case:** Bit error rate validation for signal integrity
- **UI rendering:** Live error count chart with running BER calculation

### 4. Error Injection + Recovery
- **Input:** port_id, error_type (choice: dllp-crc, tlp-lcrc, seq-num, ack-nack, cto)
- **Duration:** ~5s
- **Steps:**
  1. Read initial LTSSM state (expect L0)
  2. Read initial event counters (baseline)
  3. Inject the selected error
  4. Wait 500ms
  5. Re-read LTSSM state (verify still L0 or recovered to L0)
  6. Re-read event counters (verify error was counted)
  7. Summary: injected, detected, recovered (pass/fail)
- **Use case:** Verify error detection and recovery paths work
- **UI rendering:** Before/after comparison with pass/fail badges

### 5. Bandwidth Baseline
- **Input:** port_ids (multi-select), sample_count (default 10), interval_s (default 1.0)
- **Duration:** sample_count * interval_s
- **Steps:**
  1. Initial clear read (baseline)
  2. Loop: sample bandwidth, yield per-port egress/ingress totals
  3. Summary: average, peak, min for each port
- **Use case:** Establish performance baseline, detect bottlenecks
- **UI rendering:** Live bandwidth chart (already scaffolded in ui/pages/performance.py)

### 6. Port Equalization Report
- **Input:** port_id, link (current/previous, default current)
- **Duration:** ~3s
- **Steps:**
  1. Read TX coefficients (local end)
  2. Read TX coefficients (far end)
  3. Read EQ table with FOM values
  4. Read FS/LF values
  5. Read receiver calibration (CTLE, DFE taps)
- **Use case:** Full equalization snapshot for debug or documentation
- **UI rendering:** Table view with coefficient values per lane

### 7. Config Space Dump
- **Input:** pdfid
- **Duration:** ~2s
- **Steps:**
  1. Read PCI header (vendor/device ID, command, status)
  2. Walk capability list (offset 0x34 pointer chain)
  3. Identify PCIe capability, AER capability offsets
  4. Read key registers (Link Control, Link Status, AER status)
  5. Summary: formatted config space dump
- **Use case:** Quick endpoint identification and status check
- **UI rendering:** Formatted register table with field decode

---

## Module Structure

```
src/serialcables_switchtec/core/workflows/
|-- __init__.py           # Exports RECIPE_REGISTRY, get_recipe()
|-- models.py             # RecipeResult, RecipeSummary, RecipeParameter, StepStatus
|-- base.py               # Recipe ABC
|-- link_health.py        # LinkHealthCheckRecipe
|-- eye_scan.py           # EyeDiagramQuickScanRecipe
|-- ber_soak.py           # BerSoakTestRecipe
|-- inject_recover.py     # ErrorInjectionRecoveryRecipe
|-- bandwidth.py          # BandwidthBaselineRecipe
|-- eq_report.py          # PortEqualizationReportRecipe
+-- config_dump.py        # ConfigSpaceDumpRecipe
```

### Registry Pattern

```python
# src/serialcables_switchtec/core/workflows/__init__.py

from serialcables_switchtec.core.workflows.link_health import LinkHealthCheckRecipe
from serialcables_switchtec.core.workflows.eye_scan import EyeDiagramQuickScanRecipe
# ... etc

RECIPE_REGISTRY: dict[str, type[Recipe]] = {
    "link_health_check": LinkHealthCheckRecipe,
    "eye_diagram_quick_scan": EyeDiagramQuickScanRecipe,
    "ber_soak_test": BerSoakTestRecipe,
    "error_injection_recovery": ErrorInjectionRecoveryRecipe,
    "bandwidth_baseline": BandwidthBaselineRecipe,
    "port_eq_report": PortEqualizationReportRecipe,
    "config_space_dump": ConfigSpaceDumpRecipe,
}

def get_recipe(name: str) -> type[Recipe]:
    """Look up a recipe by name."""
    if name not in RECIPE_REGISTRY:
        raise KeyError(f"Unknown recipe: {name}. Available: {list(RECIPE_REGISTRY)}")
    return RECIPE_REGISTRY[name]
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
1. Workflows page lists all recipes from `RECIPE_REGISTRY` as cards
2. User selects a recipe card → parameter inputs appear (auto-generated from `recipe.parameters()`)
3. User clicks Run → UI calls `recipe.run(dev, **params)` in a background thread
4. Each yielded `RecipeResult` is pushed to the UI via NiceGUI's `ui.timer` or async update
5. Stepper shows: step name, status badge (green/red/yellow), detail text
6. On completion, `RecipeSummary` is rendered as a header badge (e.g., "5/5 PASSED")

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
from serialcables_switchtec.testing import create_mock_device
from serialcables_switchtec.core.workflows import get_recipe

def test_link_health_check_all_pass():
    result = create_mock_device()
    dev, fake_lib = result.device, result.fake_lib

    # Configure mocks for happy path
    fake_lib.switchtec_status.return_value = 0
    # ... configure other mocks

    recipe = get_recipe("link_health_check")()
    results = list(recipe.run(dev, port_id=0))

    assert all(r.status == StepStatus.PASS for r in results)

def test_link_health_check_link_down():
    # Configure mock for link-down port
    # Verify step 1 returns FAIL with appropriate detail
    ...
```

---

## Implementation Priority

When implementation begins (after UI is further along):

1. **Phase 1:** Models + base class + Link Health Check recipe (simplest, validates the pattern)
2. **Phase 2:** Bandwidth Baseline + BER Soak Test (monitoring-focused, uses existing watch generators)
3. **Phase 3:** Error Injection + Recovery (composition of inject + monitor + verify)
4. **Phase 4:** Eye Diagram Quick Scan (depends on UI chart rendering being ready)
5. **Phase 5:** Port EQ Report + Config Space Dump (read-heavy, table rendering)

Each phase is independently shippable. Phase 1 establishes the pattern; phases 2-5 are parallel-implementable.

---

## Open Questions (resolve during implementation)

1. **Cancellation:** Should recipes support cancellation mid-run? The BER soak test runs for user-defined duration. A `threading.Event` cancel token passed to `run()` would allow graceful stop.

2. **Persistence:** Should recipe results be saved to disk? For demos, a "last 10 runs" history in the dashboard would be valuable. Could use SQLite or simple JSON files.

3. **Custom recipes:** Should users be able to define their own recipes via YAML/JSON config files? Deferred — start with hardcoded recipes, add configurability if users request it.

4. **Parallel recipes:** Can multiple recipes run simultaneously on the same device? The `device_op()` lock serializes C calls, so recipes are thread-safe, but concurrent recipes would interleave steps unpredictably. Recommend: one recipe per device at a time, enforced by the UI/API.
