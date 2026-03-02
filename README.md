# Signal Logic

Rhythmic, antifragile operating system for signal observation, governance, and execution.

Not alerting. Not metrics. Phase alignment across domains.

---

## What it is

Signals from unrelated domains — system, market, weather, cyber — are projected onto shared oscillatory clocks. When they arrive at the same phase simultaneously, that is convergence. Convergence is recorded, not acted on.

This distinction is the system's sovereignty line. It prevents the stack from becoming a brittle control system.

---

## Design laws

| Law | Statement |
|---|---|
| **Append-only truth** | The penstock is never mutated. History is sovereign. |
| **Deterministic field** | Same time input → same field output, always. No randomness, no historical lookup. |
| **No backflow** | The Turbine observes. It never influences the Gate or the Penstock. |
| **Oracle has no authority** | The Oracle describes phase geometry only. It makes zero decisions. |
| **Antifragile tracking** | Drift, brittleness, strain, and unknowns index are recorded every cycle. |

---

## Hydro cycle

```
Observe → Gate → Dispatch → Commit → Turbine
```

| Step | Role |
|---|---|
| **Observe** | Collect packets from all active domains |
| **Gate** | Structurally validate and enqueue |
| **Dispatch** | Route to dispatch lanes: main, spillway, or reject |
| **Commit** | Seal validated Waves and append to the penstock (the immutable JSONL ledger) |
| **Turbine** | Read the committed record; detect cross-domain phase convergence |

The penstock is not a lane — it is the ledger. Lanes are dispatch routes. The Turbine is a reader, not a writer.

---

## Clock architecture

**Field clocks** — universal slow reference, computed from time alone:

| Clock | Period |
|---|---|
| Longwave | multi-year |
| Seasonal | ~365 days |
| Diurnal | 24 hours |
| Semi-diurnal | 12 hours |

**Domain stacks** — local fast probe clocks, defined per domain:

| Domain | Example stack |
|---|---|
| Cyber | burst → minute → session |
| Maritime | tide cycle → voyage → seasonal |
| Market | intraday → weekly → quarterly |

Field clocks are the reference layer. Domain stacks are how each domain speaks to that reference.

---

## Memory architecture

| Layer | Type | Description |
|---|---|---|
| **Scar** | Persistent | Long-decay historical imprints — what events left marks |
| **Ghost** | Ephemeral | Per-cycle change detection — what shifted right now |
| **Afterglow** | Resonance | Delayed activation — signals still echoing after an event |

---

## Key concepts

| Concept | Description |
|---|---|
| **Wave** | Immutable record: `(domain, channel, phase_external, phase_field, phase_diff, coherence)` |
| **Field** | Deterministic sovereign oscillatory field. Input: time. Output: phase. |
| **Penstock** | Append-only JSONL ledger. Committed Waves are sealed and never rewritten. |
| **Turbine** | Cross-domain convergence detector. Observes only — no write authority. |
| **Oracle** | Describes phase alignment geometry. No decision authority. |
| **Antifragile state** | Drift, brittleness, strain, and unknowns index tracked per cycle. |

---

## Packages

```
signal_core/    — Hydro orchestrator (observe → gate → dispatch → commit → turbine)
rhythm_os/      — Physics substrate (field, wave, memory, antifragile, PSR transforms)
apps/           — Oracle layers, scope tools, PSR ingress
config/         — YAML contracts (oracle, governance, deployment)
signal_light_press/ — Archival doctrine (non-executable memory)
```

---

## Quick start

```bash
pip install -e .
pip install -e ".[analytics]"   # adds pandas/numpy for memory modules and market transforms

signallogic-run                  # single cycle
signallogic-run --loop 60        # cadence every 60 s
signallogic-run --health         # exit 0=warm  1=cold  2=error
signallogic-dashboard            # three-tier visualization (snapshot / watch / animate)
signallogic-meter                # background continuous telemetry
```

---

## Docker

```bash
docker compose up --build

# meter     — continuous telemetry (2 s samples)
# cycle     — full cycle loop (60 s interval)
# dashboard — manual / on-demand
```

---

## Status

Python 3.11+ — pytest — 486 passing — 51% coverage

```bash
pip install -e ".[all]"
pytest
pytest --cov=src --cov-report=term-missing
```
