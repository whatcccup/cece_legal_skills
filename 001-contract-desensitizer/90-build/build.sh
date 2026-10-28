#!/bin/bash
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The SkillHub package now contains download guidance, not a duplicate engine.
python3 - "$SKILL_DIR" <<'PYZIP'
import sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]);pkg=root/'03-skillhub';out=root/'90-build/contract-desensitizer-offline.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name in ['SKILL.md']:
  z.write(pkg/name,name)
print(out)
PYZIP
if command -v skillhub >/dev/null 2>&1; then skillhub publish "$SKILL_DIR/03-skillhub" --dry-run; fi
