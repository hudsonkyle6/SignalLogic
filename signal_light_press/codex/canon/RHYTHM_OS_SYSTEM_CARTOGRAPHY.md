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
Authority: Signal Light Press
Classification: CROWN JEWEL
Status: CANONICAL
Domain: Codex
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
# Rhythm OS — System Cartography
**Status:** Canonical (Descriptive)  
**Authority:** None  
**Scope:** Structural, mathematical, jurisdictional  
**Warning:** This document explains *where things live*. It does not grant permission to act.

---

## 1. The Kernel (rhythm_os/core)

**What it is**  
The kernel is the **irreducible observational engine** of Rhythm OS. It is sovereign, unattended, and indifferent to use-cases.

**What lives here**
- **Bottom / Physics**: deterministic oscillatory invariants (diurnal, seasonal, longwave)
- **Wave**: the atomic observational record (immutable, hashed, sealed)
- **Field**: superposition of oscillatory cycles at time *t*
- **Dark Field**: append-only memory substrate (historical truth, no recall authority)
- **Memory (afterglow, ghost)**: decay descriptors only, not meaning

**What the kernel never does**
- No APIs
- No sensors
- No semantics
- No prediction
- No decision
- No optimization
- No human input
- No backfilling

The kernel answers only one question:

> *“What is the oscillatory state of the world, given time?”*

---

## 2. Mathematics & Theory (Kernel-Level)

### 2.1 Oscillatory Foundation
Each canonical cycle is defined by a period \( T_i \) and angular frequency:

\[
\omega_i = \frac{2\pi}{T_i}
\]

At time \( t \), the phase is:

\[
\phi_i(t) = (\omega_i t) \bmod 2\pi
\]

Each cycle contributes a unit phasor:

\[
z_i(t) = e^{j\phi_i(t)}
\]

---

### 2.2 Composite Field
The composite field is the vector sum:

\[
Z(t) = \sum_{i=1}^{N} z_i(t)
\]

From this:

- **Composite phase**:
\[
\Phi(t) = \arg(Z(t))
\]

- **Coherence** (normalized):
\[
C(t) = \frac{|Z(t)|}{N}
\]

This is a **dimensionless order parameter**, not a score, not a signal, not a trigger.

---

### 2.3 Drift (Optional, Descriptive Only)

When comparing two times \( t \) and \( t-\Delta t \):

\[
\dot{C} = \frac{C(t) - C(t-\Delta t)}{\Delta t}
\]

\[
\dot{\Phi} = \frac{\mathrm{wrap}(\Phi(t) - \Phi(t-\Delta t))}{\Delta t}
\]

These are **observations**, not trends, not forecasts.

---

### 2.4 Wave Integrity
A Wave is sealed by a deterministic hash:

\[
H = \mathrm{SHA256}(\text{canonicalized payload})
\]

- Payload uses **string-stabilized floats**
- Timestamp is a stored fact, never regenerated
- Verification recomputes hash from stored fields only

This makes Waves:
- Immutable
- Verifiable
- Transportable
- Non-authoritative

---

## 3. Adapters

**What they are**  
Adapters are **interfaces to reality**.

**They may**
- Read clocks
- Accept human text
- Read sensors or markets
- Touch files or networks

**They may only output**
- **Waves**

Adapters are translators, not interpreters.

They answer:
> *“How do we express this external observation as a Wave?”*

---

## 4. Domain Layer

**Where meaning begins**

Domain modules:
- Group Waves
- Name contexts (Sea, Market, Human, Memory, etc.)
- Apply *descriptive framing*

They still:
- Do not decide
- Do not act
- Do not command

Domain answers:
> *“What kind of thing is this Wave among other Waves?”*

---

## 5. Oracle

**Oracle is geometry, not prophecy**

Oracle:
- Compares phase relationships
- Describes convergence, divergence, absence
- Emits **descriptive states**, never instructions

Oracle answers:
> *“How are these oscillations relating?”*

Not:
> *“What should be done?”*

---

## 6. Shepherd

**The first place authority may exist**

Shepherd:
- Receives descriptions from below
- Applies posture doctrine
- Outputs only **posture** (e.g., SILENT, HOLD, REFUSE)

Shepherd does not:
- Execute
- Optimize
- Explain itself

Shepherd answers:
> *“Is action permitted?”*

---

## 7. Execution & Interfaces

Above Shepherd:
- Interfaces
- Reports
- Dashboards
- Human workflows
- Organizations

These are **civilizational layers**, not OS layers.

They may act — but only because **humans choose to**, not because the system commands it.

---

## 8. Codex, Seals, Chronicles (Memory of Meaning)

These folders are **not part of the OS**.

They exist to:
- Preserve doctrine
- Freeze decisions
- Record why boundaries exist
- Prevent future erosion

They answer:
> *“Why is the system shaped this way?”*

Not:
> *“What should the system do next?”*

---

## 9. What This Cartography Is Not

- Not a runtime dependency
- Not an authority source
- Not a configuration
- Not a control surface
- Not an optimization guide

This map **describes terrain**.  
It does not grant passage.

---

## Canonical One-Sentence Summary

**Rhythm OS is a physics-first, oscillatory observation system whose kernel records immutable Waves, whose middle layers describe relationships without authority, and whose highest layer permits or refuses action only through explicit, human-aligned posture — with all meaning, memory, and power carefully separated in space.**

## Domain Layer Cartography

The Domain layer is the boundary between kernel-grade oscillatory truth and any
downstream interpretation. It is the lawful interface where external domain
signals may be represented as relational objects without importing semantics,
thresholds, or authority.

### Domain Objects

**DomainWave**
- Purpose: represent phase-relationship descriptors between an external oscillator
  (domain signal) and internal field cycles (diurnal → longwave).
- Constraints:
  - no semantics (no “good/bad”)
  - no thresholds
  - no decisions
  - explicit `field_cycle` required
  - serialization must be deterministic (if persisted)

**DomainPass**
- Purpose: routing placeholder (structural stub)
- Current posture: intentionally empty
- Constraints:
  - no IO
  - no persistence
  - no outputs beyond structured stubs

**Persistence edges (domain-only, not kernel)**
- Append-only JSONL writers are permitted at the domain edge *only* when
  bootstrapped externally. Absence of paths is lawful silence.

---

## Antifragile Layer Cartography (Descriptive Pressure)

The Antifragile layer computes normalized **pressure descriptors** that quantify
exposure and deviation without implying action. It is not governance. It is not
posture. It is not “safety.” It is a descriptive lens for downstream layers.

### Files and Roles

**`drift.py`**
- Output: `drift_index ∈ [0,1]`
- Meaning: normalized deviation of a current scalar relative to a baseline window.
- Properties:
  - deterministic
  - no thresholds, no decisions
  - empty baseline normalizes to maximal deviation (1.0) as absence-of-reference

**`strain.py`**
- Output: `strain_index ∈ [0,1]`
- Meaning: conservative envelope of recent vs historical reference magnitude with
  caller-supplied attenuation coefficient (`rest_factor`) that is explicitly not
  physiological or evaluative.
- Properties:
  - deterministic
  - missing references normalize to maximal value (1.0)
  - geometric saturation only

**`brittleness.py`**
- Output: `brittleness_index ∈ [0,1]`
- Meaning: conservative envelope across normalized components:
  - irreversible commitments (proportion)
  - dependency gaps (proportion)
  - unknowns (normalized external index)
- Properties:
  - deterministic
  - missing references normalize to maximal contribution
  - max() aggregation is envelope selection (not alarm logic)

**`state.py`**
- Output: a descriptive record aggregating antifragile indices:
  - `unknowns_index`
  - `drift_index`
  - `strain_index`
  - `brittleness_index`
- Constraint: aggregation only; no interpretation, no gating, no persistence.

### Antifragile Output Contract (Stable)

Antifragile yields a dictionary of normalized indices:

- `unknowns_index ∈ [0,1]`
- `drift_index ∈ [0,1]`
- `strain_index ∈ [0,1]`
- `brittleness_index ∈ [0,1]`

Interpretation, posture, or action is strictly downstream.

---

## Mathematical Appendix (Descriptive-Only)

This appendix formalizes what the antifragile metrics *are* in mathematical terms
without smuggling interpretation.

### A. Normalization Primitive

Define saturation to the unit interval:

\[
\mathrm{clamp}_{[0,1]}(x)=
\begin{cases}
0 & x \le 0 \\
x & 0 < x < 1 \\
1 & x \ge 1
\end{cases}
\]

This is used purely as geometric normalization.

### B. Drift Index (Normalized Deviation)

Given a baseline window \(B = \{b_i\}_{i=1}^n\) and a current scalar \(c\):

\[
\mu_B = \frac{1}{n}\sum_{i=1}^n b_i,\quad
\sigma_B = \sqrt{\frac{1}{n}\sum_{i=1}^n (b_i-\mu_B)^2}
\]

\[
z = \frac{|c-\mu_B|}{\sigma_B}
\]

Define a dimensionless scaling constant \(s>0\) (drift_scale):

\[
\mathrm{drift}(c,B)=\min\left(\frac{z}{s},1\right)
\]

Edge cases:
- \(n=0\) (no reference) → drift = 1.0 (max normalized deviation)
- \(\sigma_B=0\) → drift = 0.0 (zero dispersion baseline)

### C. Strain Index (Envelope + Attenuation)

Let \(r\) be recent magnitude and \(H\) be history window, with mean \(\mu_H\).
Define envelope selection:

\[
\mathrm{raw} = \max(r,\mu_H)
\]

Let \(a\in[0,1]\) be caller-supplied attenuation coefficient (rest_factor):

\[
\mathrm{adjusted} = \mathrm{raw}\cdot (1-a)
\]

\[
\mathrm{strain} = \mathrm{clamp}_{[0,1]}(\mathrm{adjusted})
\]

Missing references normalize to 1.0 by contract.

### D. Brittleness Index (Component Enveloping)

Let components be normalized independently:

\[
C = \mathrm{clamp}_{[0,1]}\left(\frac{\mathrm{irreversible}}{\max(S,1)}\right),\quad
D = \mathrm{clamp}_{[0,1]}\left(\frac{\mathrm{gaps}}{\max(G,1)}\right),\quad
U = \mathrm{clamp}_{[0,1]}(\mathrm{unknowns})
\]

Where \(S\) and \(G\) are total slot/check capacities.

Aggregate via conservative envelope:

\[
\mathrm{brittleness}=\max(C,D,U)
\]

This is not a decision rule. It is a geometric bound on normalized exposure.

---

## Scientific Notes (Why These Cadences and Forms Are Lawful)

1) **Descriptive metrics reduce complexity without enforcing action.**
   They preserve the system’s core doctrine: observation precedes interpretation.

2) **Unit-interval normalization enables cross-channel comparability**
   without asserting ontological equivalence. It is a coordinate system, not a truth claim.

3) **Envelope selection (\(\max\)) models dominant exposure**
   without implying “badness.” It is a conservative bound that resists false comfort.

4) **Absence of reference data is not treated as error at this layer.**
   It is normalized explicitly to maximal contribution so downstream layers can
   see uncertainty rather than hiding it.

This appendix is descriptive only and confers no authority.

— END OF DOCUMENT —
SEAL: 22da5a110ead83c1afe9b9cd91580e842525ae8c509eb870b676e726474ddb75
