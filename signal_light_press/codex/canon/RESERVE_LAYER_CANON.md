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
---

## 1. Purpose

The Reserve Layer exists to describe **viability under load**.

It does not predict.  
It does not advise.  
It does not decide.

It answers only:  
> “What is the current structural exposure of the system?”

---

## 2. Canonical Metrics (Frozen)

The Reserve Layer consists of exactly four metrics:

1. **Drift Index**
   - Measures normalized deviation from recent baseline
   - Domain: antifragile
   - Channel: drift_index

2. **Brittleness Index**
   - Measures structural exposure to unknowns and commitments
   - Domain: antifragile
   - Channel: brittleness_index

3. **Strain Index**
   - Measures dominant load magnitude over recent history
   - Domain: antifragile
   - Channel: strain_index

4. **State Index**
   - Conservative envelope across drift, brittleness, and strain
   - Domain: antifragile
   - Channel: state_index

No additional Reserve metrics are permitted without canon amendment.

---

## 3. Metric Properties (Binding)

All Reserve Layer outputs MUST:

- Be normalized to the unit interval [0, 1]
- Use conservative envelope logic
- Be append-only DomainWave records
- Include extractor metadata
- Carry no thresholds, alerts, or semantics

---

## 4. Non-Implications (Critical)

Reserve Layer metrics do NOT imply:

- readiness  
- urgency  
- danger  
- action  
- permission  

They are **descriptive fields only**.

---

## 5. Relationship to Other Layers

- Reserve Layer reads from: dark_field (recent history)
- Reserve Layer writes to: dark_field (append-only)
- Reserve Layer does not read oracle outputs
- Reserve Layer does not gate execution

Alignment layers may *observe* Reserve outputs.  
Application layers may *reference* Reserve outputs.  
Neither may alter them.

---

## 6. Silence Clause

If insufficient data exists:
- metrics may default to conservative maxima
- silence is acceptable
- no synthetic smoothing is permitted

---

## 7. Freeze Clause

This canon freezes:
- metric count
- metric names
- metric semantics
- normalization rules

All changes require formal canon revision under Signal Light Press.

— END OF DOCUMENT —
SEAL: 2db0887ca9b9b6eeec1dd8ea9053cdb85a0ecb344db42258c29b9f3d0994ddb7
