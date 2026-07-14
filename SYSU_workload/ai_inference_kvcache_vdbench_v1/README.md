# SYSU AI 推理 KV cache Vdbench 冷热负载

这是 12 节点、三副本环境使用的 750 GiB 版本。它不运行真实 LLM，
而是用 Vdbench 表达 KV cache 的 active、next 和 prefix 三类生命周期，
以及 prefill/decode 的访问方式差异。

## 来源与边界

KV cache 生命周期来自 vLLM/PagedAttention（SOSP 2023，CCF-A），存储侧
benchmark 语义参考 MLPerf Storage KV Cache。详细映射见
[`../../new_workload/ai_inference_kvcache_vdbench_v1/SOURCES.md`](../../new_workload/ai_inference_kvcache_vdbench_v1/SOURCES.md)。

PagedAttention 支持 KV cache 的动态增长、持续使用和跨请求共享，但没有给出
固定的热容量与访问比例。Zipf(0.99)、三组等容量、rank 数和阶段时长是工程
执行模型。正式阶段为纯读，KV 文件只在造数据阶段生成。

## 数据构造

| 数据组 | 容量 | 逻辑 rank | 文件数 | 语义 |
|---|---:|---:|---:|---|
| `kv_active` | 250 GiB | 20 | 24,800 | 当前请求/会话 |
| `kv_next` | 250 GiB | 20 | 24,800 | 下一批请求 |
| `kv_prefix` | 250 GiB | 20 | 24,800 | 可复用共享前缀 |
| 合计 | 750 GiB | 60 | 74,400 | — |

每个逻辑 rank 为 12.5 GiB、1,240 个文件。4/8/16/32/64 MiB 五档文件
分别有 640/320/160/80/40 个，各占该 rank 的 2.5 GiB。

## 阶段内冷热

每组 250 GiB 按 4 MiB 等价对象计算为 64,000 个对象。对象级
Zipf(alpha=0.99) 聚合到 20 个等容量 rank 后，整数权重为：

```text
73 / 6 / 3 / 2 / 1 × 16
```

最热 rank 占活动组 5% 容量、承担 73% 阶段操作；所有 rank 均有非零访问。
active 和 next 阶段都保持组内 rank 01 最热，热点变化来自数据组切换；
prefix 的第二阶段才把最高权重从 rank 01 旋转到 rank 02。

## 正式阶段

6 个阶段各 100 秒：

| 阶段 | 访问数据 | I/O 模式 | 最高热点 |
|---|---|---|---|
| `prefill_active` | 全部 active rank | 顺序读 | active rank 01 |
| `decode_active` | 全部 active rank | 随机读 | active rank 01 |
| `prefill_next` | 全部 next rank | 顺序读 | next rank 01 |
| `decode_next` | 全部 next rank | 随机读 | next rank 01 |
| `prefix_reuse_primary` | 全部 prefix rank | 随机读 | prefix rank 01 |
| `prefix_reuse_shifted` | 全部 prefix rank | 随机读 | prefix rank 02 |

prefill/decode 的切换只改变文件内访问方式，不改变同一数据组的热点；热点数据组
每 200 秒从 active 迁移到 next，再迁移到 prefix。正式请求均为 4 MiB Direct
I/O；默认 `THREADS=1`、`FWD_RATE=max`。

## 使用

```bash
cd /home/chris/ceph-test/SYSU_workload/ai_inference_kvcache_vdbench_v1
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据目录为 `$ANCHOR_ROOT/ai_inference_kvcache_vdbench_v1`。当前配置没有
`hd=`。

## 适用范围

- 用于 KV cache 数据组迁移、复用和组内热点旋转实验。
- 不运行模型，不评价 token 生成速度或 MLPerf 成绩。
- prefill 在真实系统中会生成 KV；本负载只读取预生成数据。
- Zipf 权重不是 PagedAttention 或线上请求 trace 的实测比例。
