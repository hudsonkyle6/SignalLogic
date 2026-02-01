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

— END OF DOCUMENT —
SEAL: 26a916db0d015a4708f8078ef9b10ec7d289a45f7f0f184174a50d2445912e05
