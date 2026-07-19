#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$root"
./render_config.sh
config=rendered/run_test.vdb
if grep -Fq 'operation=create' "$config"; then
  echo "Refusing to run a config containing operation=create" >&2
  exit 1
fi
while IFS= read -r anchor; do
  [[ -d "$anchor" ]] || { echo "Missing prepared data directory: $anchor" >&2; exit 1; }
done < <(sed -n 's/^fsd=[^,]*,anchor=\([^,]*\),.*/\1/p' "$config")
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
"$vdbench_home/vdbench" -f "$config" -o "${OUTPUT_DIR:-output/run_test}"
