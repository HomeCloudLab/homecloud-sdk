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
root = Path(r"${ROOT}")
path = root / "pyproject.toml"
text = path.read_text(encoding="utf-8")
text2, n = re.subn(r'(?m)^version\s*=\s*"[^"]*"', f'version = "{ver}"', text, count=1)
if n != 1:
    raise SystemExit("pyproject.toml version not updated")
path.write_text(text2, encoding="utf-8")
print(f"pyproject.toml → {ver}")
doc = root / "go" / "doc.go"
gtext = doc.read_text(encoding="utf-8")
g2, n = re.subn(r'const Version = "[^"]*"', f'const Version = "{ver}"', gtext, count=1)
if n != 1:
    raise SystemExit("go/doc.go Version not updated")
doc.write_text(g2, encoding="utf-8")
print(f"go/doc.go → {ver}")
pom = root / "java" / "pom.xml"
ptext = pom.read_text(encoding="utf-8")
p2, n = re.subn(r"(<artifactId>homecloud-sdk</artifactId>\s*<version>)[^<]+", rf"\g<1>{ver}", ptext, count=1)
if n != 1:
    raise SystemExit("java/pom.xml version not updated")
pom.write_text(p2, encoding="utf-8")
print(f"java/pom.xml → {ver}")
jver = root / "java" / "src" / "main" / "java" / "com" / "homecloudlab" / "sdk" / "Version.java"
jtext = jver.read_text(encoding="utf-8")
j2, n = re.subn(r'VALUE = "[^"]*"', f'VALUE = "{ver}"', jtext, count=1)
if n != 1:
    raise SystemExit("Version.java not updated")
jver.write_text(j2, encoding="utf-8")
print(f"Version.java → {ver}")
PY

(
  cd "${ROOT}/js"
  npm version "${VER}" --no-git-tag-version --allow-same-version
)

echo
echo "Next:"
echo "  git add pyproject.toml js/package.json go/doc.go java/pom.xml java/src/main/java/com/homecloudlab/sdk/Version.java"
echo "  git commit -m \"Release ${VER}\""
echo "  git push origin HEAD"
echo "  git tag v${VER} && git push origin v${VER}"
echo "  git tag go/v${VER} && git push origin go/v${VER}"
echo
echo "v* publishes PyPI + npm + Java (GitHub Packages). go/v* is the Go module version (subdirectory)."
