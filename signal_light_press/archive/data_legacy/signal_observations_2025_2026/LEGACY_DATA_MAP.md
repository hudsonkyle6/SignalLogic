\# LEGACY DATA MAP — Rhythm OS



This document maps pre-canonical data directories to their authoritative meaning

under the current Rhythm OS architecture.



No files are moved or deleted by this document.



---



\## Legacy → Canonical Mapping



\### `diagnostics/`

\- \*\*Canonical meaning:\*\* `data/runtime/logs/`

\- \*\*Authority:\*\* Adapter runtime

\- \*\*Notes:\*\* Historical stderr/stdout captures. Non-authoritative.



---



\### `environment/`

\- \*\*Canonical meaning:\*\* `data/runtime/inputs/environment/`

\- \*\*Authority:\*\* Adapter ingestion

\- \*\*Notes:\*\* Raw or lightly processed environmental inputs.



---



\### `natural/`

\- \*\*Canonical meaning:\*\* `data/runtime/inputs/natural/`

\- \*\*Authority:\*\* Adapter ingestion

\- \*\*Notes:\*\* Natural rhythm source data.



---



\### `market/`

\- \*\*Canonical meaning:\*\* `data/runtime/inputs/market/`

\- \*\*Authority:\*\* Adapter ingestion

\- \*\*Notes:\*\* Market rhythm and shield inputs.



---



\### `human/`

\- \*\*Canonical meaning:\*\* `data/runtime/inputs/human/`

\- \*\*Authority:\*\* Adapter ingestion

\- \*\*Notes:\*\* Human state, ledger, and Weight \& Weather related inputs.



---



\### `historical/`

\- \*\*Canonical meaning:\*\* `data/runtime/inputs/historical/`

\- \*\*Authority:\*\* Adapter ingestion

\- \*\*Notes:\*\* Archived historical reference data.



---



\### `merged/`

\- \*\*Canonical meaning:\*\* `data/snapshots/`

\- \*\*Authority:\*\* Pipeline snapshot (pre-Core era)

\- \*\*Notes:\*\* Former “daily truth” files. Now treated as derived, non-authoritative snapshots.



---



\### `journal/`

\- \*\*Canonical meaning:\*\* `data/projections/journal/`

\- \*\*Authority:\*\* Projection layer

\- \*\*Notes:\*\* Human-facing reductions and journals.



\#### `journal/quarantine/`

\- \*\*Canonical meaning:\*\* `data/projections/journal/quarantine/`

\- \*\*Authority:\*\* Projection error handling

\- \*\*Notes:\*\* Explicitly non-authoritative, preserved for audit.



---



\### `oracle/`

\- \*\*Canonical meaning:\*\* `data/ml/oracle/`

\- \*\*Authority:\*\* Lighthouse / speculative

\- \*\*Notes:\*\* Predictive oracle outputs. Never upstream.



---



\### `models/`

\- \*\*Canonical meaning:\*\* `data/ml/models/`

\- \*\*Authority:\*\* Lighthouse / speculative

\- \*\*Notes:\*\* Trained ML artifacts.



---



\### `signal\_company/posture/`

\- \*\*Canonical meaning:\*\* `data/exports/reports/`

\- \*\*Authority:\*\* Interface / presentation

\- \*\*Notes:\*\* Narrative posture reports for human consumption.



---



\## Enforcement Rule



From this point forward:

\- No new files are written to legacy top-level folders

\- All new writes use canonical `data/` subdirectories

\- Legacy folders remain read-only history unless explicitly migrated



---



\## Closing Principle



Legacy data is \*\*evidence\*\*, not authority.



Authority now flows from:

`Core → Dark Field → Domain → Projections → Interfaces`



