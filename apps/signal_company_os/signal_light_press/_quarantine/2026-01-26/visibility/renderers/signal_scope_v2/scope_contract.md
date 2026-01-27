Authority: Signal Light Press
Classification: Internal
Scope: Observational Export Boundary
Status: Canonical

SIGNAL SCOPE — EXPORT CONTRACT

PURPOSE

This contract defines the only permitted data interface between
Signal Scope observational instruments and downstream renderers.

This contract preserves non-authority, non-computation, and lineage integrity.

────────────────────────────────────────

EXPORT FORM

Exported artifacts MUST:

- Be derived from sealed Wave objects
- Contain only numeric, already-computed fields
- Be windowed by omission only
- Be immutable once written

Permitted formats:
- CSV
- JSON (flat, numeric-only)
- Parquet (numeric-only)

────────────────────────────────────────

REQUIRED FIELDS

Each row MUST contain:

- t               (timestamp; addressed, not owned)
- coherence       (0–1)
- phase_spread    (radians)
- buffer_margin   (0–1)
- persistence     (non-negative integer)

────────────────────────────────────────

OPTIONAL FIELDS

Renderers may consume if present:

- drift           (signed, unitless)
- afterglow       (0–1)

No optional field may alter interpretation of required fields.

────────────────────────────────────────

PROHIBITIONS

Exported artifacts MUST NOT:

- Contain labels, regimes, or postures
- Contain thresholds or classifications
- Contain derived decisions
- Reference system state, policy, or governance
- Be re-imported upstream

────────────────────────────────────────

AUTHORITY

This contract is binding under Signal Light Press.

All renderers are subordinate to this interface.
No renderer may expand or reinterpret this contract.




