\# STATE — TELEMETRY (REPORTING ONLY)



Authority: Signal Light Press (Kernel)

Steward: Sage OS (Knowing)

Classification: Protected Internal

Status: Canonical



This directory contains system telemetry and descriptive indices.



Allowed:

\- Write health indicators and readouts (readiness\_index, drift\_index, system\_health).

\- Store Sage internal status (sage\_state.json).

\- Support integrity checks and reporting.



Forbidden:

\- No state->action translation

\- No triggers, alarms that cause workflow

\- No automatic escalation language

\- No “permission” logic (belongs to Shepherd)



Invariant:

State is observation. Permission is Shepherd.



