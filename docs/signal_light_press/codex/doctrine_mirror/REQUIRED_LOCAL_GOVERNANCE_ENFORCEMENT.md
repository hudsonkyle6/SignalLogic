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
SEAL: 9e9c9f2259d0e273c38a31e1862042934b2cd98d773fd5ee832c4deee82b3858
