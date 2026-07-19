#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
"$root/render_config.sh" >/dev/null
cd "$root/../.."
python3 -m unittest discover -s no_migration_workload/tests -v
