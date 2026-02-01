\# LEGACY DATA — FROZEN



As of: 2026-01-18



All legacy data directories under `data/` that predate the Dark Field

architecture are now \*\*frozen\*\*.



\## What “Frozen” Means



\- No new files are written to legacy folders

\- Existing files are preserved as historical evidence

\- Legacy data is never used as upstream input

\- Legacy data may be inspected or migrated deliberately later



\## Scope



Frozen legacy directories include (but are not limited to):



\- diagnostics/

\- environment/

\- natural/

\- market/

\- human/

\- historical/

\- merged/

\- journal/

\- oracle/

\- models/

\- signal\_company/



\## Canonical Rule Going Forward



All new data writes must target one of:



\- `data/dark\_field/`

\- `data/runtime/`

\- `data/snapshots/`

\- `data/projections/`

\- `data/exports/`

\- `data/ml/`

\- `data/inspection/`



Any write outside these paths is a violation.



---



Legacy is memory.

Dark Field is truth.



