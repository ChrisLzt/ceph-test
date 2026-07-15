# AI 推理 KV cache 冷热负载

## 来源与设计逻辑

KV cache 生命周期来自 vLLM/PagedAttention 的 *Efficient Memory Management
for Large Language Model Serving with PagedAttention*（SOSP 2023，CCF-A）；
存储侧类别参考 MLPerf Storage KV Cache。来源支持 cache 动态增长、decode
持续复用和跨请求/prefix 共享，但没有给出固定热容量与访问比例。文件级
Zipf(0.99) 是受控实验参数，详见 [SOURCES.md](SOURCES.md)。

## 数据构造

| 数据组 | 单元 | 容量 | rank | 每 rank 容量 |
|---|---:|---:|---:|---:|
| `kv_active` | 800 | 37.5 GiB | 80 | 480 MiB |
| `kv_next` | 800 | 37.5 GiB | 80 | 480 MiB |
| `kv_prefix` | 800 | 37.5 GiB | 80 | 480 MiB |

每 rank 为 10 单元，包含 40 个 4 MiB、20 个 8 MiB 和 10 个 16 MiB 文件。
每个固定大小档独立计算 Zipf(0.99)，再聚合到 80 个等容量 rank。

## 正式阶段

| 阶段 | 数据 | 模式 | Zipf 头 | 时长 |
|---|---|---|---:|---:|
| `prefill_active` | active | 顺序读 | rank 1 | 100 s |
| `decode_active` | active | 随机读 | rank 1 | 100 s |
| `prefill_next` | next | 顺序读 | rank 1 | 100 s |
| `decode_next` | next | 随机读 | rank 1 | 100 s |
| `prefix_reuse_primary` | prefix | 随机读 | rank 1 | 100 s |
| `prefix_reuse_shifted` | prefix | 随机读 | rank 2 | 100 s |

prefill 与 decode 的切换只改变文件内部访问方式；active 和 next 各自的两阶段
热点不变。active→next、next→prefix 与 prefix rank 1→2 均在 RD 边界直接
切换。六个阶段合计 600 秒。所有请求为 4 MiB Direct I/O、`fwdrate=max`。

## 适用范围

适合观察 KV cache 组间迁移、decode 复用和 prefix 内热点变化；不运行 LLM、
不评价 token 吞吐，也不模拟 prefill 实际写入。

数据默认位于 `/mnt/cephfs/ai_inference_kvcache_vdbench_v1`。
