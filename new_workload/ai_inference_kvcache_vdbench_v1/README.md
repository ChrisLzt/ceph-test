# AI 推理 KV cache vdbench Zipfian 冷热识别负载 v1

这个负载不运行真实 LLM，也不评价 token 生成速度。它把 LLM 推理系统中 KV cache 的明确读写行为映射成 vdbench 对 CephFS 的阶段化读写，用于冷热识别。

核心逻辑：

- prefill 阶段生成/写入当前请求的 KV cache；
- decode 阶段反复读取已有 KV cache；
- 下一批请求会生成新的 KV cache，热点迁移；
- 共享前缀或多轮对话会复用旧 KV cache；
- KV cache 访问存在偏斜，使用 Zipfian rank 表达“少量 rank 更频繁访问，但所有 rank 都会被访问”。

## 来源

主来源：

- vLLM/PagedAttention：`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023。论文说明 LLM serving 中 KV cache 很大、动态增长，并在生成阶段被持续使用；PagedAttention 用块化方式管理 KV cache，并支持跨请求/分支的 cache sharing。

补充来源：

- MLPerf Storage KV Cache：MLCommons Storage 中针对 KV-cache I/O 的官方 benchmark 类别，用于说明 KV cache 已被 MLPerf Storage 纳入存储侧 benchmark 范围。

本目录使用 vdbench 执行这些读写阶段。vdbench 不是负载来源，只是把设定好的文件读写模型落到 CephFS 上。Zipfian 是当前实验用来表达访问偏斜的执行模型，不声明为论文给出的固定比例。

详细映射见 [SOURCES.md](SOURCES.md)。

## 默认数据路径和容量

默认数据路径：

```text
/mnt/cephfs/ai_inference_kvcache_vdbench_v1/
```

默认容量为 120 GiB：

| 数据集 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `kv_active_rank_01~08` | 8 × 5 | 1 GiB | 40 GiB | 当前请求/会话 KV cache |
| `kv_next_rank_01~08` | 8 × 5 | 1 GiB | 40 GiB | 下一批请求 KV cache，热点迁移目标 |
| `kv_prefix_rank_01~08` | 8 × 5 | 1 GiB | 40 GiB | 可复用的 prefix KV cache |

### 数据构造由来

三类 KV cache 分别表达三个不同生命周期：

- `kv_active_rank_01~08`：当前请求/会话的 KV cache；
- `kv_next_rank_01~08`：下一批请求生成的新 KV cache，用于制造热点迁移；
- `kv_prefix_rank_01~08`：共享前缀、多轮对话或分支推理中可复用的旧 KV cache。

每类 KV cache 都按 8 个等容量 rank 切分。每个 rank 为 5 GiB，可看作 1280 个 4 MiB object；每类 KV cache 合计 40 GiB，即 10240 个 4 MiB object。这样可以在保持总容量 120 GiB 的同时，让每一类 KV cache 都有完整的偏斜访问长尾。

KV cache 访问偏斜采用 Zipf(alpha=0.99)。alpha=0.99 是 YCSB 常用 Zipfian 参数，表达“少量对象访问更多，但长尾对象仍会被访问”。脚本先按每类 10240 个 4 MiB object 计算 Zipf(0.99)，再聚合到 8 个等容量 rank。聚合后的 rank 访问占比约为 `78.0% / 7.3% / 4.3% / 3.1% / 2.4% / 1.9% / 1.6% / 1.4%`，vdbench 中整数化为 `79/7/4/3/2/2/2/1`。

这个容量和权重不是 PagedAttention 或 MLPerf 给出的实测热 KV cache 比例；它是用 PagedAttention 的 KV cache 生命周期语义，结合 YCSB Zipfian 分布构造的冷热识别执行模型。

## 工作流

```bash
cd /home/chris/ceph-test/new_workload/ai_inference_kvcache_vdbench_v1

./validate_model.sh
./prepare_data.sh
./run_test.sh
```

含义：

- `render_config.sh`：根据当前环境变量渲染 vdbench 配置。
- `prepare_data.sh`：只造数据，运行 `rendered/prepare_data.vdb`，包含 `format=(clean,only)` 和 `format=(restart,only)`。
- `run_test.sh`：只跑测试，运行 `rendered/run_test.vdb`，不包含任何 `format=`。
- `validate_model.sh`：只做本地配置和模型检查，不写 CephFS。

数据已经造好后，重复冷热测试只执行：

```bash
./run_test.sh
```

不要每次测试前重复运行 `prepare_data.sh`，否则会重置数据历史。

## 测试阶段

默认 6 个阶段，每阶段 100 秒，总正式测试时间 10 分钟。

```text
prefill_active
-> decode_active
-> prefill_next
-> decode_next
-> prefix_reuse_primary
-> prefix_reuse_shifted
```

| 阶段 | 读/写 | 访问数据 | 目的 |
|---|---|---|---|
| `prefill_active` | 写 | 全部 `kv_active_rank_01~08` | 当前请求 prefill 生成 KV cache |
| `decode_active` | 读 | 全部 `kv_active_rank_01~08` | decode 持续读取当前 KV cache |
| `prefill_next` | 写 | 全部 `kv_next_rank_01~08` | 下一批请求 prefill，热点迁移目标写入 |
| `decode_next` | 读 | 全部 `kv_next_rank_01~08` | decode 读取下一批 KV cache，观察热点迁移 |
| `prefix_reuse_primary` | 读 | 全部 `kv_prefix_rank_01~08` | 共享前缀/多轮对话复用旧 KV cache |
| `prefix_reuse_shifted` | 读 | 全部 `kv_prefix_rank_01~08` | prefix 热点 rank 旋转，观察旧 KV cache 热点变化 |

### 阶段由来

`prefill_active` 和 `prefill_next` 来自 LLM serving 的 prefill 过程：新请求会生成 KV cache，因此在存储侧表达为写入。这里拆成 active/next 两组，是为了让热点从当前请求迁移到下一批请求。

`decode_active` 和 `decode_next` 来自 autoregressive decode：生成 token 时会持续使用已有 KV cache，因此在存储侧表达为读取。decode 阶段使用随机读，是为了表示不同请求、不同 block/rank 的 cache 访问，而不是单个大文件顺序扫描。

`prefix_reuse_primary` 和 `prefix_reuse_shifted` 来自 PagedAttention 支持的 KV block sharing：共享前缀、多轮对话或分支推理会复用旧 KV cache。第二个 prefix 阶段旋转最高权重 rank，用于观察旧 KV cache 内部热点变化。

prefill 阶段使用顺序写；decode 和 prefix reuse 阶段使用随机读。所有阶段在各自 KV cache 类型内部使用 Zipfian 访问偏斜，不再设置完全不访问的 KV 数据池。

## 可调参数

```bash
ANCHOR=/mnt/cephfs/ai_inference_kvcache_vdbench_v1 THREADS=8 FORMAT_THREADS=4 PHASE_SECONDS=100 FWD_RATE=1000 KV_READ_XFER_SIZE=1m KV_WRITE_XFER_SIZE=4m ./render_config.sh all
```

默认 `THREADS=8`，允许多线程。单节点 SN350 上如果 Ceph 出现 backfill、recovery 或 slow ops，应先停止测试，等 `ceph -s` 恢复 `active+clean` 后再运行。

## 适用范围

- 这不是正式 MLPerf Storage 结果。
- 这不是 LLM 推理性能 benchmark。
- 论文和官方 benchmark 提供读写语义；vdbench 的 `xfersize`、线程数、容量缩放是当前实验环境参数。
- Zipf(alpha=0.99) 采用 YCSB 常用参数；这里按 4 MiB object 计算后聚合到 vdbench rank，不是 PagedAttention 或 MLPerf 给出的实测热 KV cache 容量/访问比例。
