#!/usr/bin/env bash
# Bump Python + Node SDK versions together, then print the release tag command.
# Usage: ./scripts/bump-version.sh 0.5.0
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-}"
if [[ ! "$VER" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-].*)?$ ]]; then
  echo "Usage: $0 <semver>   e.g. $0 0.5.0" >&2
  exit 1
fi

python - <<PY
from pathlib import Path
import re
ver = "${VER}"
path = Path(r"${ROOT}") / "pyproject.toml"
text = path.read_text(encoding="utf-8")
text2, n = re.subn(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{ver}"', text, count=1)
if n != 1:
    raise SystemExit("pyproject.toml version not updated")
path.write_text(text2, encoding="utf-8")
print(f"pyproject.toml → {ver}")
PY

(
  cd "${ROOT}/js"
  npm version "${VER}" --no-git-tag-version --allow-same-version
)

echo
echo "Next:"
echo "  git add pyproject.toml js/package.json"
echo "  git commit -m \"Release ${VER}\""
echo "  git push origin HEAD"
echo "  git tag v${VER}"
echo "  git push origin v${VER}"
echo
echo "That single tag runs Publish to PyPI + Publish to npm (same version)."
