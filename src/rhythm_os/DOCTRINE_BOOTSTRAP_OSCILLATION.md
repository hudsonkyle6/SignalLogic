# DOCTRINE — Bootstrap Oscillation

POSTURE: CANONICAL

This doctrine defines the expected behavior of the system during initial activation,
before upstream oscillatory phase is fully coupled into Hydro.

---

## Definitions

**Penstock**
Append-only, immutable Wave storage. One Wave per line (JSONL). Never overwritten.

**Bootstrap Wave**
A Wave committed during early activation where oscillatory descriptors may be
nominal or defaulted (e.g., phase = 0.0).

**Energy Emergence**
The expected transition from mean oscillatory energy near 0.0 toward non-zero
values as committed Waves begin to carry real phase information.

---

## Non-Negotiable Invariants

1. **Append-only truth**
   - Previously committed Waves are never altered or removed.
   - Early zero-energy Waves remain forever and are not “cleaned.”

2. **Windowed observation**
   - Any diagnostic that summarizes “current state” must consider a window
     of recent Waves, not a single record.
   - `head` shows oldest truth; `tail` shows newest truth.

3. **Zero energy is healthy at boot**
   - If phase = 0.0 then `|sin(phase)| = 0` and energy may be 0.0.
   - This is expected and indicates no fabricated signal.

4. **No backflow**
   - Turbine output never influences Hydro admission or routing.
   - Observation does not become authority.

---

## Verification Procedure (Bootstrap)

After a Hydro run commits Waves to the Penstock:

1. Confirm newest committed Wave:
   - `tail -n 1 src/rhythm_os/data/dark_field/penstock/*.jsonl`

2. Confirm append-only history remains intact:
   - `head -n 1 src/rhythm_os/data/dark_field/penstock/*.jsonl`

3. Run Turbine probe:
   - `PYTHONPATH=src python src/rhythm_os/turbine/probe.py`

Expected:
- Committed waves observed: >= 1
- Mean oscillatory energy: may be 0.0 early, becomes > 0.0 as non-zero phase commits accumulate

---

## Exit Criteria (Bootstrap Complete)

Bootstrap oscillation is considered complete when:

- Hydro commits Waves with non-zero phase originating from upstream Rhythm computation (not hardcoded),
- Turbine reports stable non-zero energy over a recent window,
- No module violates directionality:
  Tributary → Hydro → Penstock → Turbine
