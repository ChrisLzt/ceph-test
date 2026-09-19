#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' '此 SINGLE v1 执行入口已停用。请使用 SINGLE_workload/graph_graphchi_psw_v2/prepare_data.sh；旧数据不会自动删除。' >&2
exit 2
