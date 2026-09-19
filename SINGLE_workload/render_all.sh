#!/usr/bin/env bash
set -euo pipefail
suite=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$suite/single_current.sh" render "$@"
