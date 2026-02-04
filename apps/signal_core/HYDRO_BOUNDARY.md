# HYDRO — Boundary & Authority Contract (v1)

Status: Canonical Boundary
Executable: No
Scope: Signal Core / Hydro Substrate
Effective: 2026-02-03

## 1) System Statement
Hydro is a non-agentive control substrate. It routes pressure, preserves immutable records, and produces non-authoritative illumination. Hydro does not execute authority.

## 2) Hard Prohibitions (Global)
Hydro MUST NOT:
- interpret meaning at ingress or routing layers
- learn inside ingress gate or dispatcher
- optimize routing decisions
- bypass gates
- rewrite memory
- execute actions (network, filesystem changes, API calls with side-effects) without an explicit, human-signed execution gate downstream of Hydro

## 3) Topology (Closed)
Ingress Gate → Dispatcher → (Main | Spillway | Turbine) → Lighthouse → Dark Field → Helmsman (voiced; non-executable)

## 4) Component Authority
### Ingress Gate
- PASS | QUARANTINE | REJECT
- Structural checks only: schema, provenance, freshness, legibility, lane admissibility
- NO interpretation, NO optimization

### Dispatcher (Keystone)
- Deterministic routing only
- Routes pressure, not decisions
- No learning, no inference
- No upstream routing from any downstream channel

### Main Channel
- Production flow
- Stable and boring
- Zero experiments
- No diverted pressure

### Spillway
- Pressure relief / mitigation
- Rate limiting, buffering, temporary isolation
- No learning
- No memory writes (except append-only routing logs already defined)

### Auxiliary Turbine
- Receives quarantined signals, diverted pressure, simulations, replays
- Never touches production
- Never routes upstream
- Never executes authority

### Lighthouse
- Read-only illumination and pattern lens
- Computes bounded descriptors; labels outputs as observations/proposals
- Cannot write truth; cannot overwrite records

### Dark Field
- Append-only immutable memory
- Stores admitted packets, routing outcomes, and labeled summaries

### Helmsman (Emergent)
- Interpretive surface only
- Cannot execute, escalate, bypass gates, or rewrite memory

## 5) Allowed Writes
Only append-only records to Dark Field with explicit record types:
- ingress_record
- dispatch_record
- lighthouse_summary (labeled)
- human_signature (optional)

## 6) Versioning Discipline
Changes to this boundary require:
- a dedicated commit
- explicit rationale in commit message
- no co-mingled runtime changes

