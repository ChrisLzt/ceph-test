# 五类冷热识别负载来源与设计摘要

本文档简要说明 5 类 CephFS 冷热识别负载的来源、设计逻辑、测试数据分布、测试阶段和适用范围与限制。当前目标不是复现原生应用性能，也不是提交标准 benchmark 成绩，而是在负载特征合理、来源可追溯的前提下，构造可观察的冷热变化。

## 总览

| 类型 | 目录 | 工具 | 默认容量 | 默认正式测试时间 | 数据路径 |
|---|---|---|---:|---:|---|
| 大数据 | `bigdata_mapreduce_vdbench_v1` | vdbench | 约 117.19 GiB | 10 min | `/mnt/cephfs/bigdata_mapreduce_vdbench_v1` |
| 图计算 | `graph_graphchi_vdbench_v1` | vdbench | 约 112.50 GiB | 10 min | `/mnt/cephfs/graph_graphchi_vdbench_v1` |
| HPC | `hpc_wrf_ior_v1` | IOR | 约 112.00 GiB | 约 10 min | `/mnt/cephfs/hpc_wrf_ior_v1` |
| AI 训练 | `ai_training_checkpoint_vdbench_v1` | vdbench | 约 112.00 GiB | 10 min | `/mnt/cephfs/ai_training_checkpoint_vdbench_v1` |
| AI 推理 | `ai_inference_kvcache_vdbench_v1` | vdbench | 约 112.00 GiB | 10 min | `/mnt/cephfs/ai_inference_kvcache_vdbench_v1` |

## 1. 大数据：MapReduce 文件冷热负载

### 来源

- Cristina L. Abad 等，`A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal Locality and Arrival Patterns`，IEEE IISWC 2012（按 ccf.atom.im 2026 第七版目录：未收录）。
- 研究对象是 Yahoo! Hadoop/MapReduce 生产 trace。

### 设计逻辑

论文给出了 MapReduce 文件 popularity、temporal locality、inactive storage 等观测。v1 使用论文中 temporal-locality 的容量/访问关系构造文件池热点：少量年轻/活跃文件池获得主要访问，背景文件池维持低热度，inactive 文件池全程不访问。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `pool_01` | 200 | 12 MiB | 约 2.34 GiB | 轮转热点 A |
| `pool_02` | 200 | 12 MiB | 约 2.34 GiB | 轮转热点 B |
| `pool_03` | 200 | 12 MiB | 约 2.34 GiB | 轮转热点 C |
| `pool_04` | 5000 | 12 MiB | 约 58.59 GiB | 活跃背景数据 |
| `pool_05` | 4400 | 12 MiB | 约 51.56 GiB | inactive 冷数据 |

### 测试阶段

默认 4 个阶段各 150 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问的数据 | 访问分布 | 目的 |
|---|---|---|---|---|
| `hot_a` | 读 | `pool_01`、`pool_02`、`pool_03`、`pool_04` | 85% / 1% / 1% / 13% | `pool_01` 成为热点 |
| `hot_b` | 读 | `pool_01`、`pool_02`、`pool_03`、`pool_04` | 1% / 85% / 1% / 13% | 热点从 `pool_01` 迁移到 `pool_02` |
| `hot_c` | 读 | `pool_01`、`pool_02`、`pool_03`、`pool_04` | 1% / 1% / 85% / 13% | 热点从 `pool_02` 迁移到 `pool_03` |
| `reheat_a` | 读 | `pool_01`、`pool_02`、`pool_03`、`pool_04` | 85% / 1% / 1% / 13% | `pool_01` 复热 |

`pool_05` 在全部正式测试阶段不读写，作为 inactive 冷数据对照。

### 适用范围与限制

- vdbench 只负责把文件池读写施加到 CephFS。
- 不能声称复现完整 Hadoop/HDFS 行为。
- 论文中的 open/access 不能直接等价为真实 read bytes。

## 2. 图计算：GraphChi shard 热点迁移负载

### 来源

- Kyrola、Blelloch、Guestrin，`GraphChi: Large-Scale Graph Computation on Just a PC`，OSDI 2012（CCF-A）。

### 设计逻辑

GraphChi 的 Parallel Sliding Windows 会把图划分为 shard/interval。当前 interval 对应的 memory-shard 会被完整读取，其他 shard 根据 sliding window 读取部分数据。v1 不手写热点比例，而是先生成一张确定性 graph，再根据 GraphChi PSW 规则计算每个阶段的 shard 访问比例。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `shard_00` | 1800 | 16 MiB | 约 28.13 GiB | interval 0 对应 shard |
| `shard_01` | 1800 | 16 MiB | 约 28.13 GiB | interval 1 对应 shard |
| `shard_02` | 1800 | 16 MiB | 约 28.13 GiB | interval 2 对应 shard |
| `shard_03` | 1800 | 16 MiB | 约 28.13 GiB | interval 3 对应 shard |

默认 generated graph 只用于推导访问比例；实际 112.50 GiB 测试容量由 vdbench shard 文件池承担。

### 测试阶段

默认 8 个阶段各 75 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问的数据 | 访问分布 | 目的 |
|---|---|---|---|---|
| `iter1_i0` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 75% / 13% / 6% / 6% | interval 0 的 memory-shard 为主热点 |
| `iter1_i1` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 6% / 75% / 13% / 6% | 热点迁移到 interval 1 |
| `iter1_i2` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 6% / 6% / 75% / 13% | 热点迁移到 interval 2 |
| `iter1_i3` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 13% / 6% / 6% / 75% | 热点迁移到 interval 3 |
| `iter2_i0` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 75% / 13% / 6% / 6% | 第二轮重新访问 interval 0，形成复热 |
| `iter2_i1` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 6% / 75% / 13% / 6% | 第二轮重新访问 interval 1 |
| `iter2_i2` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 6% / 6% / 75% / 13% | 第二轮重新访问 interval 2 |
| `iter2_i3` | 读 | `shard_00`、`shard_01`、`shard_02`、`shard_03` | 13% / 6% / 6% / 75% | 第二轮重新访问 interval 3 |

图计算负载没有手工指定热点比例；这些分布由 generated graph 经 GraphChi PSW 规则计算后写入 vdbench 配置。

### 适用范围与限制

- 不运行 GraphChi 程序。
- 不执行 PageRank 等图算法计算。
- 默认 generated graph 是受控输入，不代表真实生产图比例。
- 当前负载模拟的是边 shard 的访问热度变化，不模拟完整顶点属性更新、message passing 或 checkpoint。

## 3. HPC：WRF checkpoint/restart 负载

### 来源

- NSF NCAR/MMM WRF v3.9.1.1 CONUS-12km benchmark 语义。
- WRF 是典型 MPI HPC weather simulation 应用。
- IOR 官方 parallel I/O benchmark 用作执行工具。

### 设计逻辑

WRF 运行涉及输入文件、边界文件、restart/checkpoint 文件和 history/output 文件。checkpoint/history 具有明确生命周期：写入后短期热，恢复时旧 checkpoint 复热，旧 history 可作为冷背景。v1 使用 IOR file-per-process 表达 MPI 并行 I/O。

### 测试数据分布

| 数据组 | 文件语义 | 默认容量 | 作用 |
|---|---|---:|---|
| `input/wrfinput_d01` | 初始气象场 | 约 16 GiB | 启动阶段读取 |
| `input/wrfbdy_d01` | 边界场 | 约 16 GiB | 启动阶段读取 |
| `restart/wrfrst_initial` | 初始 restart | 约 16 GiB | 启动阶段读取 |
| `checkpoint/wrfrst_old` | 旧 checkpoint | 约 16 GiB | 恢复阶段复热 |
| `history/wrfout_old` | 旧 history/output | 约 16 GiB | 冷背景 |
| `checkpoint/wrfrst_current` | 当前 checkpoint | 约 16 GiB | 写后热读 |
| `history/wrfout_current` | 当前 history/output | 约 16 GiB | 写后热读 |

默认 `NP=4`、file-per-process、每 rank 4 GiB，因此每个文件语义组约 16 GiB。

### 测试阶段

默认 8 次 IOR 阶段调用，每阶段通过 IOR `-D 75` 控制，总正式测试时间约 10 分钟。IOR 需要额外启动/收尾开销，因此实际墙钟时间可能略高。

| 阶段 | 读/写 | 访问的数据 | 目的 |
|---|---|---|---|
| `startup_read_wrfinput` | 读 | `input/wrfinput_d01` | 模拟 WRF 启动读取初始气象场 |
| `startup_read_wrfbdy` | 读 | `input/wrfbdy_d01` | 模拟 WRF 启动读取边界场 |
| `startup_read_restart` | 读 | `restart/wrfrst_initial` | 模拟从 restart 文件初始化 |
| `checkpoint_write_current` | 写 | `checkpoint/wrfrst_current` | 模拟运行过程中写当前 checkpoint |
| `checkpoint_hot_read_current` | 读 | `checkpoint/wrfrst_current` | 模拟 checkpoint 写出后短期被读取/校验，形成写后热读 |
| `history_write_current` | 写 | `history/wrfout_current` | 模拟写当前 history/output |
| `history_hot_read_current` | 读 | `history/wrfout_current` | 模拟 history/output 写出后短期读取 |
| `recovery_reheat_read_old_checkpoint` | 读 | `checkpoint/wrfrst_old` | 模拟恢复时读取旧 checkpoint，形成复热 |

`history/wrfout_old` 在正式测试阶段不读写，作为冷背景数据。

### 适用范围与限制

- 不运行真实 WRF 模型。
- 不模拟 NetCDF/HDF5 内部变量布局。
- 不复现真实 CONUS-12km 原始文件大小。
- 只保留 HPC 文件生命周期和并行 I/O 语义。

## 4. AI 训练：数据读取与 checkpoint 负载

### 来源

- Meta DSI / ISCA 2022（CCF-A）：`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`。
- MLPerf Storage checkpointing / DLIO。

### 设计逻辑

Meta DSI 描述大规模训练会反复读取、过滤数据，并存在热门 features/samples。MLPerf Storage checkpointing / DLIO 提供 checkpoint write/read/recovery 的存储语义。v1 将训练数据读取和 checkpoint 生命周期组合成阶段化 vdbench 负载。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `dataset_hot` | 32 | 1 GiB | 32 GiB | 训练阶段主要读取的数据 |
| `dataset_warm` | 24 | 1 GiB | 24 GiB | 较低热度训练数据 |
| `dataset_cold` | 32 | 1 GiB | 32 GiB | 不访问的冷训练数据 |
| `checkpoint_current` | 12 | 1 GiB | 12 GiB | 当前 checkpoint，写后读 |
| `checkpoint_old` | 12 | 1 GiB | 12 GiB | 旧 checkpoint，恢复阶段复热 |

### 测试阶段

默认 5 个阶段各 120 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问的数据 | 目的 |
|---|---|---|---|
| `epoch_read_hot_dataset` | 读 | `dataset_hot` | 模拟训练 epoch 中主要训练数据被反复读取 |
| `epoch_read_warm_dataset` | 读 | `dataset_warm` | 模拟较低热度训练数据读取 |
| `checkpoint_write_current` | 写 | `checkpoint_current` | 模拟训练过程中写当前 checkpoint |
| `checkpoint_read_current` | 读 | `checkpoint_current` | 模拟当前 checkpoint 写后读取/校验 |
| `recovery_read_old_checkpoint` | 读 | `checkpoint_old` | 模拟故障恢复或恢复训练时读取旧 checkpoint，形成复热 |

`dataset_cold` 在正式测试阶段不读写，作为冷训练数据对照。

### 适用范围与限制

- 不运行真实模型训练。
- 不评价 GPU/训练吞吐。
- 论文和 MLPerf 提供读写语义，但没有给出可直接落地的热数据容量占比和访问占比。
- 容量分布是当前单节点实验预算下的缩放参数，不是论文固定比例。

## 5. AI 推理：LLM KV cache 负载

### 来源

- vLLM/PagedAttention：`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023（CCF-A）。
- MLPerf Storage KV Cache benchmark 类别。

### 设计逻辑

LLM 推理中，prefill 会生成 KV cache，decode 阶段会持续读取已有 KV cache。多轮对话、共享前缀或分支推理会复用旧 KV cache。v1 将这些行为映射为 KV cache 文件池的写入、读取、热点迁移和复热。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `kv_active` | 32 | 1 GiB | 32 GiB | 当前请求/会话 KV cache |
| `kv_prefix_reuse` | 32 | 1 GiB | 32 GiB | 旧 KV cache，prefix reuse 阶段复热 |
| `kv_next` | 32 | 1 GiB | 32 GiB | 下一批请求 KV cache |
| `kv_cold` | 16 | 1 GiB | 16 GiB | 不访问的冷 KV cache |

### 测试阶段

默认 5 个阶段各 120 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问的数据 | 目的 |
|---|---|---|---|
| `prefill_write_active` | 写 | `kv_active` | 模拟当前请求 prefill 生成并写入 KV cache |
| `decode_read_active` | 读 | `kv_active` | 模拟 decode 阶段反复读取当前 KV cache |
| `prefill_write_next` | 写 | `kv_next` | 模拟下一批请求生成新的 KV cache |
| `decode_read_next` | 读 | `kv_next` | 模拟下一批请求进入 decode，热点迁移到新 KV cache |
| `prefix_reuse_read_old` | 读 | `kv_prefix_reuse` | 模拟共享前缀/多轮对话读取旧 KV cache，形成复热 |

`kv_cold` 在正式测试阶段不读写，作为冷 KV cache 对照。

### 适用范围与限制

- 不运行真实 LLM。
- 不评价 token 生成速度。
- PagedAttention 支撑 KV cache 行为模型，但没有给出热 KV cache 的固定容量/访问比例。
- 容量分布是当前单节点实验预算下的缩放参数，不是论文固定比例。
