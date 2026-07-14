# AI 推理 KV cache 负载来源与映射

## 1. vLLM / PagedAttention，SOSP 2023

论文：

- Woosuk Kwon 等，`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023。
- arXiv: <https://arxiv.org/abs/2309.06180>

采用的负载逻辑：

- LLM serving 的 KV cache 很大，并随请求动态增长；
- prefill 会产生当前请求的 KV cache；
- decode/autoregressive generation 会持续使用已有 KV cache；
- PagedAttention 将 KV cache 组织为块，并支持跨请求或分支共享 KV cache；
- 为构造可控冷热，本实验额外使用 Zipfian rank 表达访问偏斜；该分布是工程模型，不是 PagedAttention 论文结论。

映射到本负载：

| 论文/系统现象 | vdbench 映射 |
|---|---|
| prefill 阶段 KV cache | `prefill_active` / `prefill_next` 读取预生成数据 |
| decode 使用已有 KV cache | `decode_active` / `decode_next` 随机读 |
| KV cache 可跨请求/分支共享 | `prefix_reuse_primary` / `prefix_reuse_shifted` 随机读 |
| 访问存在偏斜但长尾仍有访问 | 对每类 KV cache 的 20 个 rank 施加 Zipfian skew |

## 2. MLPerf Storage KV Cache

官方来源：

- MLCommons Storage：<https://github.com/mlcommons/storage>

采用的负载逻辑：

- MLPerf Storage 已经把 KV Cache 作为独立存储 benchmark 类别；
- 这说明 KV cache I/O 是 AI 推理存储侧值得单独建模的负载。

本目录不运行 MLPerf Storage 官方流程，只保留 KV cache 存储语义，并用 vdbench 落到 CephFS。

## 3. 为什么使用 vdbench + Zipfian

当前目标是冷热识别，不是提交 MLPerf 成绩，也不是复现 vLLM 推理性能。Vdbench 在造数据阶段创建固定容量文件，正式阶段按顺序读或随机读访问这些文件；Zipfian skew 能表达“少量 KV rank 访问更多，但长尾 rank 仍然被访问”的偏斜访问。

需要明确的适用范围：

- 目录名不使用 `mlperf`，因为这里不运行官方 MLPerf Storage closed/open 流程；
- `THREADS`、`xfersize`、容量缩放是执行参数，不是论文参数；
- PagedAttention 论文说明 KV cache 动态增长、decode 持续使用已有 KV cache、并支持跨请求/分支共享，但没有给出“热 KV cache 占总容量 X%、承担总访问 Y%”这种可直接落地的固定比例；
- 当前 Zipfian 权重采用 YCSB 常用 alpha=0.99。脚本按 4 MiB object 计算 Zipf(0.99)，再聚合到每类 KV cache 的 20 个等容量 rank，整数化为 `68/7/4/3/2/2/1×14`；后续可由公开 trace 提取结果替换；
- MLPerf Storage KV Cache 说明 KV cache 是独立存储 benchmark 类别，但它的参数用于 benchmark 运行，不等价于真实线上冷热容量/访问比例；
- 热/冷判断由测试者根据阶段语义和 Ceph 观测结果自行判断，不在脚本中生成真值表。
