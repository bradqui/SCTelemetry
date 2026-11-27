#!/bin/sh
# Print one release's section of CHANGELOG.md (the lines under "## <version> (...)", up to
# the next "## "), without its heading. Fails if there's no such section or it's empty.
#   .github/scripts/changelog.sh 0.10.6 [CHANGELOG.md]
set -eu
version="$1"
file="${2:-CHANGELOG.md}"
section=$(awk -v v="$version" '
  /^## / { if (found) exit; found = ($2 == v) ; next }
  found { print }
' "$file" | sed -e '/./,$!d')
section=$(printf '%s\n' "$section" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')
if [ -z "$(printf '%s' "$section" | tr -d '[:space:]')" ]; then
  echo "::error::CHANGELOG.md has no section for $version: add \"## $version (<date>)\" with what changed." >&2
  exit 1
fi
printf '%s\n' "$section"
