# AI 推理 KV cache 负载来源与映射

## 1. vLLM / PagedAttention，SOSP 2023

论文：

- Woosuk Kwon 等，`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023。
- arXiv: <https://arxiv.org/abs/2309.06180>

采用的负载逻辑：

- LLM serving 的 KV cache 很大，并随请求动态增长；
- prefill 会产生当前请求的 KV cache；
- decode/autoregressive generation 会持续使用已有 KV cache；
- PagedAttention 将 KV cache 组织为块，并支持跨请求或分支共享 KV cache。

映射到本负载：

| 论文/系统现象 | vdbench 映射 |
|---|---|
| prefill 生成 KV cache | `prefill_write_active` / `prefill_write_next` |
| decode 使用已有 KV cache | `decode_read_active` / `decode_read_next` |
| KV cache 可跨请求/分支共享 | `prefix_reuse_read_old` |
| 不再访问的 KV cache | `kv_cold` 只造数据，不在 run 阶段访问 |

## 2. MLPerf Storage KV Cache

官方来源：

- MLCommons Storage：<https://github.com/mlcommons/storage>

采用的负载逻辑：

- MLPerf Storage 已经把 KV Cache 作为独立存储 benchmark 类别；
- 这说明 KV cache I/O 是 AI 推理存储侧值得单独建模的负载。

本目录不运行 MLPerf Storage 官方流程，只保留 KV cache 存储语义，并用 vdbench 落到 CephFS。

## 3. 为什么使用 vdbench

当前目标是冷热识别，不是提交 MLPerf 成绩，也不是复现 vLLM 推理性能。vdbench 能稳定地在 CephFS 上创建固定容量文件，并按阶段执行读写，因此适合将上述来源中的 KV cache 语义简化为可控冷热模型。

需要明确的边界：

- 目录名不再使用 `mlperf`，因为这里不运行官方 MLPerf Storage closed/open 流程；
- `THREADS`、`xfersize`、容量缩放是执行参数，不是论文参数；
- PagedAttention 论文说明 KV cache 动态增长、decode 持续使用已有 KV cache、并支持跨请求/分支共享，但没有给出“热 KV cache 占总容量 X%、承担总访问 Y%”这种可直接落地的固定比例；
- MLPerf Storage KV Cache 说明 KV cache 是独立存储 benchmark 类别，但它的参数用于 benchmark 运行，不等价于真实线上冷热容量/访问比例；
- 热/冷判断由测试者根据阶段语义和 Ceph 观测结果自行判断，不在脚本中生成真值表。
