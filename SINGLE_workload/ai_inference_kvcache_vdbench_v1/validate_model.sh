#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
"$root/render_config.sh" all >/dev/null
cd "$root/../.."
python3 -m unittest workload_common.tests.test_ai_inference -v
