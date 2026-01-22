#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------
# Normalize all doctrinal mirrors
# Signal Company OS — Engine Room
# ----------------------------------

ENGINE_ROOM_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ENGINE_ROOM_DIR/../../.." && pwd)"

NORMALIZER="$ENGINE_ROOM_DIR/normalize_doctrine_headers.py"

echo "Normalizing doctrinal mirrors (read-only sources enforced)"
echo

python "$NORMALIZER" mirror codex/doctrine_mirror/BOUNDARY_FIELD_DOCTRINE.md
python "$NORMALIZER" mirror codex/doctrine_mirror/DREAMING_GOVERNANCE_CANON.md

echo
echo "✔ All mirrors normalized"
