\# DATA AUTHORITY — Rhythm OS



This document defines the authority and meaning of all data stored under `data/`.



\## Core Rule (Non-Negotiable)



\*\*Core truth lives ONLY in `data/dark\_field/`.\*\*



Everything else is downstream, derived, or representational.



---



\## Directory Authority Map



\### `data/dark\_field/`

\- \*\*Authority:\*\* Core-adjacent (append-only)

\- \*\*Contents:\*\* Immutable Wave records (JSONL)

\- \*\*Rules:\*\*

&nbsp; - Append-only

&nbsp; - No reads by Core

&nbsp; - No mutation

&nbsp; - No interpretation



---



\### `data/runtime/`

\- \*\*Authority:\*\* Adapters / orchestration

\- \*\*Contents:\*\* Logs, diagnostics, transient runtime artifacts

\- \*\*Rules:\*\*

&nbsp; - Ephemeral

&nbsp; - Non-authoritative

&nbsp; - Safe to delete or rotate



---



\### `data/snapshots/`

\- \*\*Authority:\*\* Domain (state capture)

\- \*\*Contents:\*\* Derived state snapshots (CSV, JSON, YAML)

\- \*\*Rules:\*\*

&nbsp; - Read-only for history

&nbsp; - Never upstream of Core

&nbsp; - Rebuildable from Dark Field



---



\### `data/projections/`

\- \*\*Authority:\*\* Projection layer

\- \*\*Contents:\*\* Journals, summaries, reductions

\- \*\*Rules:\*\*

&nbsp; - Human-facing

&nbsp; - Fallible

&nbsp; - Never used as input



---



\### `data/exports/`

\- \*\*Authority:\*\* Interface layer

\- \*\*Contents:\*\* Reports, external system exports

\- \*\*Rules:\*\*

&nbsp; - Presentation only

&nbsp; - No write-back



---



\### `data/ml/`

\- \*\*Authority:\*\* Lighthouse / speculative systems

\- \*\*Contents:\*\* Models, features, predictions

\- \*\*Rules:\*\*

&nbsp; - Non-authoritative

&nbsp; - No influence on Core or Domain



---



\### `data/inspection/`

\- \*\*Authority:\*\* Read-only forensic tools

\- \*\*Contents:\*\* Views, audits, diagnostics

\- \*\*Rules:\*\*

&nbsp; - Read-only

&nbsp; - Never feeds execution



---



\## Final Principle



> If a piece of data knows who will read it, it is not truth.



Truth is written once, silently, and never explained.



