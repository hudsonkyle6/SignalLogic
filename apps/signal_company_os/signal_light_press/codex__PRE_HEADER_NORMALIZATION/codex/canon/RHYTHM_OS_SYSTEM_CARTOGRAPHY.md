Rhythm OS — System Cartography

Status: Canonical (Descriptive)
Authority: None
Scope: Structural, Mathematical, Jurisdictional
Posture: Custodial Silence (Default)

Warning: This document explains where things live and what they are allowed to do.
It grants no permission to act.

Executive Summary

Rhythm OS is a physics-first observational operating system.

It does not decide, optimize, predict, recommend, advise, schedule, notify, or act.

Its sole function is to:

Observe oscillatory reality, preserve those observations immutably, and expose relational structure upward without authority.

All meaning, memory, judgment, and action are separated in space, not by convention but by enforced architecture.

The governing physical law of Rhythm OS is:

Change is allowed where recovery is possible.
Structure is fixed where failure is irreversible.

This is not an ethical claim.
It is a survivability constraint.

Canonical Tree (Current)
rhythm_os/
  core/
    bottom/
    wave/
    dark_field/
    memory/
  adapters/
    observe/
  domain/
    oracle/
    antifragile/
    shepherd/
    execution/
  data/
    dark_field/

1. Kernel (rhythm_os/core)
1.1 What the Kernel Is

The Kernel is the irreducible observational engine of Rhythm OS.

It is:

Sovereign

Unattended

Deterministic

Indifferent to use-cases

The Kernel answers exactly one question:

“What is the oscillatory state of the world, given time?”

1.2 What Lives in the Kernel

Bottom / Physics — deterministic oscillatory invariants (diurnal, semi-diurnal, seasonal, longwave)

Wave — atomic observational record (immutable, hashed, sealed)

Field — superposition of oscillatory cycles at time t

Dark Field — append-only historical truth (no recall authority)

Memory (afterglow, ghost) — decay descriptors only (no semantics)

1.3 What the Kernel Never Does

The Kernel has hard refusals:

No APIs

No sensors

No semantics

No prediction

No decisions

No optimization

No human input

No backfilling

The Kernel does not know why anything matters.
It only knows that oscillations exist.

2. Mathematical Foundation (Kernel-Level)
2.1 Canonical Oscillators

Each cycle has a period 
𝑇
𝑖
T
i
	​

 and angular frequency:

𝜔
𝑖
=
2
𝜋
𝑇
𝑖
ω
i
	​

=
T
i
	​

2π
	​


Phase at time 
𝑡
t:

𝜙
𝑖
(
𝑡
)
=
(
𝜔
𝑖
𝑡
)
 
m
o
d
 
2
𝜋
ϕ
i
	​

(t)=(ω
i
	​

t)mod2π

Unit phasor contribution:

𝑧
𝑖
(
𝑡
)
=
𝑒
𝑗
𝜙
𝑖
(
𝑡
)
z
i
	​

(t)=e
jϕ
i
	​

(t)
2.2 Composite Field

Vector sum of all cycles:

𝑍
(
𝑡
)
=
∑
𝑖
=
1
𝑁
𝑧
𝑖
(
𝑡
)
Z(t)=
i=1
∑
N
	​

z
i
	​

(t)

Derived quantities (descriptive only):

Composite phase:

Φ
(
𝑡
)
=
arg
⁡
(
𝑍
(
𝑡
)
)
Φ(t)=arg(Z(t))

Coherence (dimensionless order parameter):

𝐶
(
𝑡
)
=
∣
𝑍
(
𝑡
)
∣
𝑁
C(t)=
N
∣Z(t)∣
	​


These are descriptive quantities only.
They are not signals, scores, triggers, or confidence measures.

2.3 Drift (Optional, Descriptive)
𝐶
˙
=
𝐶
(
𝑡
)
−
𝐶
(
𝑡
−
Δ
𝑡
)
Δ
𝑡
C
˙
=
Δt
C(t)−C(t−Δt)
	​

Φ
˙
=
w
r
a
p
(
Φ
(
𝑡
)
−
Φ
(
𝑡
−
Δ
𝑡
)
)
Δ
𝑡
Φ
˙
=
Δt
wrap(Φ(t)−Φ(t−Δt))
	​


Drift is an observation of change, not a forecast.

2.4 Wave Integrity

A Wave is sealed by a deterministic hash:

𝐻
=
S
H
A
256
(
canonicalized payload
)
H=SHA256(canonicalized payload)

Properties:

Immutable

Verifiable

Transportable

Non-authoritative

Timestamps are stored facts and never regenerated.

3. Adapters (rhythm_os/adapters)

Adapters are interfaces to reality, not interpreters.

They may:

read clocks

accept human text

read sensors or markets

touch files or networks (in external systems, not in kernel)

They may output only:

Waves (kernel record), or

DomainWaves (phase relationship descriptors; see §4)

Adapters answer:

“How do we express this observation as a phase relationship to the sovereign field?”

They do not explain meaning.

3.1 Observe Adapters (rhythm_os/adapters/observe)

This directory contains all external signal adapters.

Rules (canonical):

External signals are guests, never authorities.

Only phase may be extracted.

Only DomainWaves may be emitted.

No posture, no thresholds, no advice.

3.1.1 Phase Extraction (phase_extractor.py)

Observe adapters may implement multiple extraction methods (e.g., Hilbert transform, zero-crossing), but all must:

return phase 
∈
[
0
,
2
𝜋
)
∈[0,2π)

return descriptive metadata only

produce no IO and no persistence

perform no scoring and no readiness assessment

3.1.2 Phase Comparison (phase_compare.py)

Phase comparison produces a DomainWave descriptor by comparing an external phase to a sovereign field component.

Critical rule:

Phase comparison is pure computation. It must never write.

This file must not accept filesystem paths or call persistence utilities.

3.1.3 Physics-Instantiated Oscillators (synthetic_multi.py)

Rhythm OS permits physics-instantiated oscillators only under strict conditions:

equations are time-tested physical primitives

provenance is explicit (domain="synthetic" and extractor metadata)

no writes, no persistence, no feedback, no learning

output is descriptive only (DomainWave objects)

This is not “simulation.”
It is a controlled instantiation of physical law for calibration and probe.

3.1.4 Package Initialization (init.py)

Observe package initialization is documentation-only.

No imports

No __all__

No convenience API aggregation

4. Domain Layer (Meaning Boundary) — rhythm_os/domain

The Domain layer is the boundary between oscillatory truth and contextual naming.

It:

groups Waves/DomainWaves

names contexts (Sea, Market, Human, Memory, etc.)

preserves plurality

Domain answers:

“What kind of thing is this relationship among other relationships?”

Domain contains:

DomainWave — phase-relationship descriptor only

DomainPass — structural routing placeholder (intentionally weak)

Write Utilities — explicit append-only persistence primitives (see §4.3)

No thresholds.
No decisions.
No actions.

4.1 DomainWave (domain_wave.py)

A DomainWave is a descriptive record of a phase relationship:

external phase

sovereign field phase

wrapped phase difference

optional descriptive coherence

extractor provenance metadata

It is not authority.
It is not a trigger.
It is not advice.

4.2 DomainPass (domain_pass.py)

DomainPass is intentionally incomplete.

accepts descriptors

returns placeholders

performs no IO

grants no permission

does not harden meaning prematurely

This enforces resistance to premature semantics.

4.3 Persistence Primitive (write.py)

rhythm_os/domain/write.py may contain a low-level append-only primitive such as:

append_domain_wave(path, wave)

This function is lawful only as a primitive.
It is not lawful for Rhythm OS to decide when or where to call it.

Most important sentence:

The instant a function causes a DomainWave to be written to an external store, it stops being a descriptor and becomes an emitter.

Therefore:

Rhythm OS functions must never call persistence as a side effect.

Persistence decisions belong to external orchestration layers.

Design constraints for write primitives:

append-only

no overwrite

no reads

no eager directory creation (caller must bootstrap persistence structure)

explicit failures (missing parent directory must be loud)

5. Oracle — Relational Geometry Without Authority (rhythm_os/domain/oracle)

Oracle is geometry, not prophecy.

It answers:

“How are these oscillations relating?”

Oracle:

compares phase relationships

describes convergence and divergence

emits descriptive alignment records

Oracle never:

decides

recommends

optimizes

signals readiness

Oracle is the last mathematical layer without consequence.

6. Antifragile Layer (Descriptive Pressure) — rhythm_os/domain/antifragile

The Antifragile layer produces normalized pressure descriptors.

Outputs (all 
∈
[
0
,
1
]
∈[0,1]):

unknowns_index

drift_index

strain_index

brittleness_index

These values describe exposure, not danger.
Absence of reference data normalizes to maximal uncertainty.

This layer does not gate, decide, or permit action.

7. Shepherd — Permission Without Action (rhythm_os/domain/shepherd)

Shepherd is the first and only layer where permission may appear.

It answers exactly one question:

“Is action permitted to exist?”

Outputs:

SILENT (default)

ALLOW

REFUSE

Shepherd:

does not act

does not explain

does not learn

does not optimize

Refusal is structural memory, not fear.

8. Execution Boundary (rhythm_os/domain/execution)

The Execution Boundary enforces separation between permission and action.

Binary mapping:

ALLOW → OPEN

SILENT / REFUSE → CLOSED

Binary gating is intentional:

Once action exists, consequences exist.

Execution remains entirely human-owned.

9. What Rhythm OS Is Not

Rhythm OS is not:

an AI

a decision engine

a control system

a predictor

an optimizer

a moral authority

a scheduler

a notifier

It is terrain, not command.

Canonical One-Sentence Summary

Rhythm OS is a physics-first observational operating system that records immutable oscillatory reality, describes relational structure without authority, and preserves human agency by separating observation, description, permission, and action in enforced architectural space.ayers.