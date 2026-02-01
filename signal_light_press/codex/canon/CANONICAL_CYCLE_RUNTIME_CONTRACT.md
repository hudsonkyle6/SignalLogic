Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
AUTHORITY: Signal Light Press
CLASSIFICATION: CANON
SCOPE: Rhythm OS + Signal Company runtime wiring
STATUS: DRAFT (Binding intent)
AMENDMENT_RULE: Signal Light Press only
EXECUTABLE: NO

# Canonical Cycle Runtime Contract — Draft v1

## 1. Definition

A cycle is the smallest unit of time the system recognizes.

A cycle:
- advances time by one step
- may produce new observations or none
- never reinterprets the past
- never guarantees output

Silence is a valid outcome.

## 2. Canonical Phase Order (fixed)

Phases may do nothing, but may not reorder.

### Phase 1 — Horizon Scan (Perception)
Purpose: Observe external reality and record it without interpretation.
Reads: external sources/sensors/feeds
Writes: DomainWave packets → data/dark_field/
Rules:
- no memory access
- no antifragile metrics
- no oracle
- no thresholds, decisions, or action semantics

### Phase 2 — Memory Core (Continuity)
Purpose: Maintain temporal coherence and decay.
Reads: dark_field (append-only)
Computes: ghost / afterglow / stability envelopes
Writes: memory envelopes → dark_field
Rules:
- cannot invent signals
- cannot suppress signals
- cannot evaluate meaning

### Phase 3 — Reserve Layer (Viability)
Purpose: Describe structural stress and exposure.
Reads: dark_field (recent window)
Computes: drift / brittleness / strain / state
Writes: antifragile envelopes → dark_field
Rules:
- normalized [0–1]
- conservative envelopes only
- no thresholds, decisions, or action semantics

### Phase 4 — Alignment Layer (Interpretation, optional)
Purpose: Translate numeric condition into symbolic geometry.
Reads: domain waves + antifragile state
Computes: alignment descriptors / convergence / phase labels (optional)
Writes: oracle descriptors → dark_field (optional)
Rules:
- descriptive only
- symbolic, not imperative
- may choose silence

### Phase 5 — Application Areas (Human-gated)
Purpose: Use descriptions to form proposals, simulations, or reports.
Reads: dark_field + oracle outputs + antifragile state
Writes: proposals/sims/reports
Rules:
- no execution without explicit human mandate
- proposals are artifacts, not commands

## 3. Non-implications

A cycle does NOT imply:
- readiness
- urgency
- correctness
- action

A cycle implies only:
"Time has passed. This is what was observed."

## 4. Binding to directory template

- 3_foundations/ defines rules cycles may not violate
- 4_modes/ implements Phases 1–4
- 7_application_areas/ consumes outputs under human gate
- bin/ is the only place a cycle may be advanced

## 5. Classification rule

Any script that cannot declare which Phase it belongs to is not runtime.

— END OF DOCUMENT —
SEAL: f146b193e49b161c087dce81f0b595f86f6803bacb0d860d9e8f27c7bf065967
