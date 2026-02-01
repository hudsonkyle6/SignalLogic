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
Scope: Signal Light Press Governance
────────────────────────────────────────

Rule:
All contributors must run local governance enforcement prior to commit.

Definition:
Local enforcement means executing the header audit defined by the
Header Contract using the official enforcement tool and policy.

Implementation:
- A local pre-commit hook MUST execute the header audit.
- Commits made without local enforcement are non-canonical.
- CI or review MAY re-run audits as a backstop; this does not replace
  local enforcement.

Rationale:
Authority must be enforced at the point of action. Memory and intent
are insufficient.

────────────────────────────────────────

— END OF DOCUMENT —
SEAL: f95675d1d78fc3f32f52a611a0a154f8c3f3aa289f906ef22312c341b17f376a
