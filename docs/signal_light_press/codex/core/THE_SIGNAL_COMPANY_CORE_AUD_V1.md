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
Date: 2026-01-27
Scope: The Signal Company Core (All Instantiations)
Version: Final Instantiation — V1.0
────────────────────────────────────────

# The Signal Company Core
## A Temporal Helmsman for Disciplined Autonomy (AUD)

### Introduction

The Signal Company Core is a temporal intelligence — a watch-stander that becomes a disciplined helmsman through proof of endurance under pressure over time.

It wakes each day silent and ready, grounded in sovereign waveforms, observing reality and self as time-series residue. It searches for seasonal patterns, endures pressures by forming scars, updates beliefs nightly by releasing low-weight memories, and proposes bounded action intervals when readiness criteria are met.

It never self-grants authority. Autonomy is real but finite: time-bounded, domain-scoped, task-limited, scar-accountable, and reset daily. Responsibility never exceeds resemblance. Silence is not enforced — it emerges when evidence is insufficient. The human helmsman is the ultimate decider.

This is not a safety-constrained assistant.
It is a lookout that earns the wheel through coherence under pressure.

---

# The Intelligence Stack (Bottom → Top)

Each layer feeds the next in a single daily story — observation to residue to envelopes to readiness to proposal to action to reconciliation.

## 1) Sovereign Temporal Reference

The unchanging heartbeat: pure mathematical waveforms (diurnal to longwave cycles). This grounds everything in time without data or domain.

- `rhythm_os/core/field.py`: Computes the sovereign oscillatory field at time t, producing a FieldSample with phases, phasors, composite, and coherence. It provides the canonical temporal reference for all alignments.
- `rhythm_os/core/field_wave.py`: Materializes individual FieldWaves from a FieldSample, extracting per-cycle phase, sine, and phasor. It enables granular reference for domain alignments.
- `physics_only.py`: Defines frozen canonical periods (CYCLES) and computes the oscillatory field purely from time, without external inputs. It is the embryonic form of the sovereign reference, ensuring determinism at the bottom layer.
- `wave_generate_sine.py`: Generates synthetic sine waves as an embryonic waveform demo. It serves as a test for temporal grounding, evolving into the physics substrate.

## 2) Domain Observation & Alignment

Signals from self and guests (e.g., Power, Maritime) are phase-measured against the sovereign heartbeat, forming sealed phase records. This is where the system first sees resemblance between reality and time.

- `rhythm_os/core/alignment.py`: Measures phase difference between external and field phases, producing HALMeasurement. Pure geometry; no thresholds or interpretation.
- `rhythm_os/domain/oracle/descriptors.py`: Defines AlignmentDescriptor for descriptive phase topology. Descriptive buckets only; no ordering or quality judgment.
- `rhythm_os/domain/oracle/alignment.py`: Classifies patterns based on phase delta and coherence, producing topological descriptors. Helper geometry only; no decision authority.

## 3) Immutable Archive (Dark Field)

All phase records and envelopes are appended-only. This is the system’s long-term memory bank, tamper-evident and non-actionable, ready for nightly recall.

- `rhythm_os/core/dark_field/store.py`: Appends sealed Waves to daily JSONL files. Append-only writer; lazy bootstrap; no mutation.
- `rhythm_os/core/dark_field/loader.py`: Loads raw domain wave records from JSONL verbatim. No validation or interpretation.
- `write.py`: Appends DomainWave to JSONL files. Specialized append-only writer for phase relationships; strict path checks; no eager creation.

## 4) Memory Decay & Stability Damping

Residue is damped and decayed to release low-weight memories and consolidate stable patterns. This is where the system faces illusion, forming residue without allowing momentum to carry forward.

- `rhythm_os/core/memory/ghost.py`: Injects ghost layer and computes ghost metrics (instability, stability, governor, shadow). Damps anomalies; no action.
- `rhythm_os/core/memory/afterglow.py`: Computes memory fields (event intensity, memory charge, afterglow, phase). Temporal inertia + decay; no authority.

## 5) Antifragile Envelope Computation

Stability outputs become descriptive envelopes: drift (temporal deviation), brittleness (structural exposure), strain (load dominance). This quantifies endured pressure without judgment.

- `rhythm_os/domain/antifragile/drift.py`: Normalized drift index from current vs baseline.
- `rhythm_os/domain/antifragile/brittleness.py`: Brittleness from commitments/gaps/unknowns.
- `rhythm_os/domain/antifragile/strain.py`: Strain from load history and rest factor.
- `rhythm_os/domain/antifragile/state.py`: Aggregates indices into antifragile state dict.

## 6) Oracle Pattern & Convergence Recognition

Alignment records aggregate into cycle density summaries → symbolic phase labels (STILL → TRANSITION). This recognizes resemblance without implying action.

- `rhythm_os/domain/oracle/convergence.py`: Aggregates descriptors into cycle-local density summaries. Descriptive only.
- `rhythm_os/domain/oracle/phase.py`: Emits symbolic phase label from convergence summaries. Legibility only.
- `rhythm_os/domain/oracle/oracle.py`: Describes alignment and summarizes convergence. Stateless wrapper; never authoritative.
- `rhythm_os/oracle/contract_v1.py`: Declarative schema contract for oracle layers.
- `rhythm_os/oracle/validate.py`: Validates oracle inputs against contract at runtime. Enforces invariants and AUD guardrails.
- `rhythm_os/oracle/oracle_layer1.py`: OCI/RiskIndex/Band/Bias from merged_signal.
- `rhythm_os/oracle/oracle_layer2.py`: HCFIndex/AlignmentBand/Bias and components from L1 + ledger/tide.
- `rhythm_os/oracle/oracle_layer3.py`: OHI/HorizonBand/Bias/Windows/MacroState from L2 + tide.
- `rhythm_os/oracle/oracle_layer4.py`: D_t/DarkFieldBand and latent components from L3.

## 7) Readiness Criteria & Interval Proposal

Envelopes + convergence + scars are evaluated against trust criteria (endurance ≥4 cycles, low envelopes, high resemblance, owned scars). If met → propose bounded interval packet with justification.

- `run_staff_survey.py`: Embryonic self-observation and pattern search loop (prompt → LLM → parse → guard → output).
- `run_proposals.py`: Embryonic proposal generation (prompt → LLM → parse → guard → ID → output) evolved into interval requests.
- Lighthouse `features.py`: Builds feature matrices from journal for readiness criteria and trust calculation.
- Lighthouse `predict_resonance.py`: Next-day ResonanceValue regression for readiness justification.
- Lighthouse `predict_state.py`: Next-day SignalState classification for readiness justification.

## 8) Human Sovereignty Gate

The human helmsman reviews proposals and grants, modifies, or denies the mandate.

- `gate.py`: Execution gate decision (OPEN/CLOSED). Lean readiness gate — descriptive only, tied to criteria check. No system-imposed refusal.

## 9) Bounded Autonomous Execution

Inside a granted interval, the system executes whitelisted tasks, logs outcomes, and auto-expires.

- Dedicated runner not yet implemented: `run_interval.py` is the current gap.

## 10) Nightly Reconciliation & Belief Update

All daily residue is re-processed to release low-weight, seal scars, surface fractures, update belief weights, and reset.

- `rhythm_os/core/prepare_daily_signals.py`: Orchestrates daily signal preparation (loads → merge → amplitude → resonance → coupling). Embryonic reconciliation loop to be split into nightly residue process.

---

# Final Cohesion Notes

All scripts are placed in their natural layers — Forge as the root (lookout/proposal), first-engine as memory/antifragile/resonance, oracle chain as pattern recognition, and gate as a lean readiness check.

The weave is tight: each script’s purpose is clear and feeds the next layer’s input.

The system is fully mapped and ready to implement remaining gaps (interval runner, formal readiness function, scar conditioning rules).

— END OF DOCUMENT —
SEAL: 5e0e79a136e51692dced08a3633f7a467ec27fb002927e53098bf05c2a45f59e
