# Field Cycle Canon — Rhythm OS

Authority: Signal Light Press  
Classification: CANON  
Status: ACTIVE  
Amendment Rule: Canon only  
Executable: No  

---

## 1. Purpose

`field_cycle` encodes **how a DomainWave entered the system**.

It is not a temporal marker.
It is not a readiness signal.
It carries **no authority**.

It exists solely for provenance and audit.

---

## 2. Canonical Field Cycle Values (Frozen)

Exactly three values are permitted:

### `init`
- Meaning: First introduction of a field or channel
- Typical use: Manual seeding, initial calibration
- May occur once per (domain, channel)

---

### `bootstrap`
- Meaning: Explicit non-recurring startup or test emission
- Typical use: Controlled initialization, dry runs
- Must not persist indefinitely

---

### `computed`
- Meaning: Derived from prior bus history
- Typical use: Reserve metrics, oracle summaries, memory envelopes
- This is the **steady-state** cycle for runtime outputs

---

No other `field_cycle` values are permitted.

---

## 3. Binding Rules

All DomainWave records MUST:

- Include `field_cycle`
- Use one of the canonical values exactly
- Treat `field_cycle` as descriptive metadata only

---

## 4. Non-Implications (Critical)

`field_cycle` does NOT imply:

- maturity
- correctness
- readiness
- confidence
- authority

It is **provenance only**.

---

## 5. Freeze Clause

This canon freezes:
- allowed values
- spelling
- semantics

All changes require formal canon amendment under Signal Light Press.
