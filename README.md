# Signal Logic

Rhythmic, antifragile operating system for signal observation, governance, and execution.

This repository contains the executable kernel (`signal_core`), the physics substrate (`rhythm_os`), and the archival doctrine layer (`signal_light_press`). Documentation and canon live alongside code, but are treated as non-executable memory.

---

## Architecture

```
signal_core/    — Hydro orchestrator: observe → gate → dispatch → commit → turbine
rhythm_os/      — Physics substrate: oscillatory field models, memory, antifragile state
apps/           — Oracle layers, ML prediction, PSR tools, signal scope
tests/          — Unit test suite (pytest)
config/         — YAML contracts (oracle, governance, deployment)
```

**Core cycle:**

1. **Observe** — collect packets from multiple domains (system, market, natural, cyber)
2. **Gate** — structurally validate and enqueue
3. **Dispatch** — route to lanes (penstock, turbine, spillway, reject)
4. **Commit** — append validated waves to the append-only JSONL penstock
5. **Turbine** — detect cross-domain phase convergence
6. **Dashboard** — three-tier visualization (snapshot / watch / animate)

Phase computation is deterministic and pure (time-only input). The penstock is append-only; history is never rewritten.

---

## Quick Start

**Install (core):**
```bash
pip install -e .
```

**Install with analytics extras** (pandas/numpy required for memory modules and market transforms):
```bash
pip install -e ".[analytics]"
```

**Run a single cycle:**
```bash
signallogic-run
```

**Run in cadence loop (every 60 s):**
```bash
signallogic-run --loop 60
```

**Check system readiness:**
```bash
signallogic-run --health
# exit 0 = warm, 1 = cold, 2 = error
```

**Launch the dashboard:**
```bash
signallogic-dashboard
```

**Start background telemetry:**
```bash
signallogic-meter
```

---

## Docker

```bash
# Build and start all services
docker compose up --build

# Services:
#   meter     — continuous telemetry (2 s samples)
#   cycle     — full cycle loop (60 s interval)
#   dashboard — manual / on-demand
```

---

## Development

**Requirements:** Python 3.11+

```bash
# Install with test dependencies
pip install -e ".[all]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing
```

---

## Key Concepts

| Concept | Description |
|---|---|
| **Penstock** | Append-only JSONL store. Committed waves are immutable. |
| **Field** | Deterministic sovereign oscillatory field computed from time alone. |
| **Wave** | Immutable record: `(domain, channel, phase_external, phase_field, phase_diff, coherence)`. |
| **Turbine** | Cross-domain convergence detector. Observes only — no authority. |
| **Antifragile state** | Tracks drift, brittleness, strain, and unknowns index per cycle. |
| **Oracle** | Describes phase alignment geometry. No decision authority. |
| **Ghost / Afterglow** | Ephemeral and persistent memory layers (analytics extra). |

---

## Packages

| Package | Purpose |
|---|---|
| `signal_core` | Hydro pipeline, dashboard, telemetry meter |
| `rhythm_os` | Field, wave, memory, antifragile domain, PSR transforms, runtime bus |
