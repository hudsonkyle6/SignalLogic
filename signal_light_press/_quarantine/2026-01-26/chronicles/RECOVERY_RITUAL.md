Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
# RECOVERY_RITUAL — Kernel Restoration Procedure

Status: Canonical (Descriptive)
Authority: Signal Light Press
Scope: Recovery / Restore / Continuity

## Goal
Restore Signal Light Press kernel to a known-good state after loss or corruption.

## Primary Truth Sources (in order)
1) Git repository history (tags/commits)
2) seals/ + _CANON_CHECKSUMS.sha256 baseline
3) chronicles/snapshots/ (time-series artifacts)
4) frozen archives (_archive_*)

## Procedure (Human)
1. Obtain clean working copy of repository.
2. Verify canonical scope file list:
   - _CANON_SCOPE.txt
   - _CANON_FILE_LIST.txt
3. Verify integrity:
   - sha256sum -c _CANON_CHECKSUMS.sha256
4. If mismatch:
   - identify changed files via diff against _CANON_CHECKSUMS.sha256
   - restore from git commit/tag OR from frozen archive snapshot
5. Re-run:
   - regenerate checksum baseline only after adjudication
   - create new seal documenting change

## Adjudication Rule
Any change to canon/doctrine requires:
- documentation of why
- new seal entry
- updated manifests (navigator + seal manifest)

— END OF DOCUMENT —
SEAL: 74e27bd0ad32ce0cf91bfe12a9a2330e6b352fee1d70a9ef4944db5c89af02eb
