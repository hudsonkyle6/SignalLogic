# Required Local Governance Enforcement

Classification: Doctrine
Scope: Signal Light Press Governance
Authority: Derived from Canon
Status: Binding

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
