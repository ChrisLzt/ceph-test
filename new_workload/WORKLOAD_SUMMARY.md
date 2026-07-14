# 五类冷热识别负载来源与设计摘要

本文档简要说明单节点 CephFS 的 5 类冷热识别负载，包括来源、设计逻辑、测试数据分布、测试阶段和适用范围。当前目标不是复现原生应用性能，也不是提交标准 benchmark 成绩，而是在负载特征合理、来源可追溯的前提下，构造可观察的冷热变化。

HPC Vdbench、AI 训练和 AI 推理当前使用 Zipfian rank 表达访问偏斜；Zipf alpha=0.99 采用 YCSB 常用参数，但该权重仍是执行模型，不是应用论文实测比例。AI 后续 trace 提取方案见 [AI_TRACE_RATIO_PLAN.md](AI_TRACE_RATIO_PLAN.md)。

## 总览

| 类型 | 目录 | 工具 | 默认容量 | 默认时间 |
|---|---|---|---:|---:|
| 大数据 | `bigdata_mapreduce`<br>`_vdbench_v1` | vdbench | 约 117.19 GiB | 10 min |
| 图计算 | `graph_graphchi`<br>`_vdbench_v1` | vdbench | 约 112.50 GiB | 10 min |
| HPC | `hpc_wrf`<br>`_vdbench_v1` | vdbench | 约 112.50 GiB | 10 min |
| AI 训练 | `ai_training_checkpoint`<br>`_vdbench_v1` | vdbench | 约 113.28 GiB | 10 min |
| AI 推理 | `ai_inference_kvcache`<br>`_vdbench_v1` | vdbench | 约 117.19 GiB | 10 min |

固定热点目录只作为诊断负载使用，不计入 5 类正式负载。

表中 HPC 采用 Vdbench 作为默认五类实现；`hpc_wrf_ior_v1` 是同一 WRF
生命周期的 MPI/file-per-process 备选实现，逻辑容量约 108 GiB，也执行
4 × 150 秒阶段。12 节点、三副本版本见
[`../SYSU_workload`](../SYSU_workload/README.md)。

## 1. 大数据：MapReduce 文件冷热负载

### 来源

- Cristina L. Abad 等，`A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal Locality and Arrival Patterns`，IEEE IISWC 2012（按 ccf.atom.im 2026 第七版目录：未收录）。
- 研究对象是 Yahoo! Hadoop/MapReduce 生产 trace。

### 设计逻辑

论文给出了 MapReduce 文件 popularity、temporal locality、inactive storage 等观测。v1 使用论文中 temporal-locality 的容量/访问关系构造文件池热点：少量年轻/活跃文件池获得主要访问，背景文件池维持低热度。为避免出现全程 0 访问数据，当前版本把旧 cold/inactive 池容量按原活跃池比例分配给三个候选热点池和背景池。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `pool_01` | 400 | 12 MiB | 约 4.69 GiB | 轮转热点 A |
| `pool_02` | 400 | 12 MiB | 约 4.69 GiB | 轮转热点 B |
| `pool_03` | 400 | 12 MiB | 约 4.69 GiB | 轮转热点 C |
| `pool_04` | 8800 | 12 MiB | 约 103.13 GiB | 活跃背景数据 |

按论文 PROD 原始容量数值计算：A/B/C 各使用 1 天内年轻文件的 2.21% bytes，cold 使用 inactive bytes 的 46%，背景池为剩余 47.37%。将 46% cold 容量按 2.21:2.21:2.21:47.37 分配给前四池后，新容量比例约为 4.09%/4.09%/4.09%/87.72%；最终取整为 4%/4%/4%/88%。

### 测试阶段

默认 4 个阶段各 150 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问数据 | 访问分布 | 目的 |
|---|---|---|---|---|
| `hot_a` | 读 | `pool_01~04` | 85% / 1% / 1% / 13% | `pool_01` 成为热点 |
| `hot_b` | 读 | `pool_01~04` | 1% / 85% / 1% / 13% | 热点迁移到 `pool_02` |
| `hot_c` | 读 | `pool_01~04` | 1% / 1% / 85% / 13% | 热点迁移到 `pool_03` |
| `reheat_a` | 读 | `pool_01~04` | 85% / 1% / 1% / 13% | `pool_01` 复热 |

当前版本不存在 `pool_05`；全部正式测试数据池都会被访问。

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

默认先执行一轮完整 interval 序列，再执行第二轮 interval 0，共 5 个阶段各 120 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问数据 | 访问分布 | 目的 |
|---|---|---|---|---|
| `iter1_i0` | 读 | `shard_00~03` | 75% / 13% / 6% / 6% | interval 0 为主热点 |
| `iter1_i1` | 读 | `shard_00~03` | 6% / 75% / 13% / 6% | 热点迁移到 interval 1 |
| `iter1_i2` | 读 | `shard_00~03` | 6% / 6% / 75% / 13% | 热点迁移到 interval 2 |
| `iter1_i3` | 读 | `shard_00~03` | 13% / 6% / 6% / 75% | 热点迁移到 interval 3 |
| `iter2_i0` | 读 | `shard_00~03` | 75% / 13% / 6% / 6% | `shard_00` 复热 |

图计算负载没有手工指定热点比例；这些分布由 generated graph 经 GraphChi PSW 规则计算后写入 vdbench 配置。前四个阶段对应一轮完整 interval 处理，最后一个阶段对应下一轮重新处理 interval 0；只保留第二轮的首个 interval 是 10 分钟测试预算下的复热设计，不是论文规定的固定阶段数。`graph_graphchi_fixed_hot_vdbench_v1` 复用同一数据集，但固定 `shard_00` 为 75% 热点，作为排查 GraphChi accuracy 是否受热点迁移影响的对照负载。

### 适用范围与限制

- 不运行 GraphChi 程序。
- 不执行 PageRank 等图算法计算。
- 默认 generated graph 是受控输入，不代表真实生产图比例。
- 当前负载模拟的是边 shard 的访问热度变化，不模拟完整顶点属性更新、message passing 或 checkpoint。

## 3. HPC：WRF 文件生命周期 Zipf 负载

### 来源

- NSF NCAR/MMM WRF v3.9.1.1 CONUS-12km benchmark 语义。
- WRF 是典型 MPI HPC weather simulation 应用。
- Vdbench 用作可控冷热执行工具；IOR 版本继续保留为 MPI/file-per-process 版本。

### 设计逻辑

WRF 运行涉及输入、边界、restart/checkpoint 和 history/output 文件。Vdbench v1 将它们组织为 startup、checkpoint、history 三个数据组；每组拆成 20 个等容量 rank，并按对象级 Zipf(0.99) 聚合权重产生阶段内冷热。checkpoint 首次读取后冷却，最后以相同 rank 顺序复热。

### 测试数据分布

| 数据组 | 文件结构 | 默认容量 | 作用 |
|---|---|---:|---|
| `startup/rank_01~20` | 20 × 120个16 MiB文件 | 约 37.5 GiB | 输入和边界状态读取 |
| `checkpoint/rank_01~20` | 20 × 120个16 MiB文件 | 约 37.5 GiB | 首次读和复热读 |
| `history/rank_01~20` | 20 × 120个16 MiB文件 | 约 37.5 GiB | history/output分析读取 |

每个 rank 容量为 1.875 GiB，每组 37.5 GiB，总容量 112.5 GiB。每组按 4 MiB 对象计算 Zipf(0.99)，再聚合到 20 个等容量 rank，整数权重为 `68/7/4/3/2/2/1×14`。最热 5% 组内容量承担 68% 阶段访问，但所有 rank 都有非零访问。该分布是执行模型，不是 WRF trace。

### 测试阶段

默认 4 个纯读阶段，每阶段 150 秒，总正式测试时间 10 分钟；使用 4 MiB 顺序文件读、Direct I/O 和 `fwdrate=1000`。`FWD_RATE=max` 仅在需要测最大吞吐时显式启用。

| 阶段 | 读/写 | 访问数据 | 目的 |
|---|---|---|---|
| `startup_read` | 读 | 全部 startup rank | startup/rank_01 为主热点 |
| `checkpoint_read` | 读 | 全部 checkpoint rank | checkpoint/rank_01 首次升温 |
| `history_read` | 读 | 全部 history rank | history/rank_01 升温、checkpoint 冷却 |
| `checkpoint_reheat` | 读 | 全部 checkpoint rank | 同一 checkpoint/rank_01 复热 |

三个数据组都会在正式测试中访问。单阶段只活动一个高层数据组，但组内 20 个 rank 全部参与读取，并由 Zipf 权重形成明确冷热。

### 适用范围与限制

- 不运行真实 WRF 模型。
- 正式测试只读，不模拟 checkpoint/history 写出。
- 不模拟 NetCDF/HDF5 内部变量布局。
- 不复现真实 CONUS-12km 原始文件大小。
- Vdbench 版本不表达 MPI/collective I/O；需要并行 I/O 语义时使用保留的 `hpc_wrf_ior_v1`。

## 4. AI 训练：数据读取与 checkpoint 负载

### 来源

- Meta DSI / ISCA 2022（CCF-A）：`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`。
- MLPerf Storage checkpointing / DLIO。

### 设计逻辑

Meta DSI 描述大规模训练会反复读取、过滤数据，并存在热门 features/samples。MLPerf Storage checkpointing / DLIO 提供 checkpoint write/read/recovery 的存储语义。v1 将训练数据读取和 checkpoint 生命周期组合成阶段化 vdbench 负载。训练数据不再划分为完全不访问的冷池，而是切成等容量 rank，用 Zipfian 权重表达访问偏斜。

数据构造上，训练数据由 20 个等容量 rank 组成，每个 rank 为 250 个 20 MiB 文件。按 4 MiB object 估算，训练数据约为 25000 个 object。先按 object 级 Zipf(alpha=0.99) 计算访问概率，再聚合到 20 个等容量 rank，得到 `69/6/4/3/2/2/1×14`。checkpoint 作为训练状态文件单独建模，不参与样本 Zipfian 分布。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `dataset_rank`<br>`_01~20` | 20 × 250 | 20 MiB | 约 97.66 GiB | 训练数据 rank，全部参与读取 |
| `checkpoint`<br>`_current` | 400 | 20 MiB | 约 7.81 GiB | 造数时创建；正式阶段重复读取 |
| `checkpoint`<br>`_old` | 400 | 20 MiB | 约 7.81 GiB | 旧 checkpoint，恢复阶段复热 |

数据读取阶段按 4 MiB object 计算 Zipf(alpha=0.99)，再聚合到 20 个 dataset rank，整数化权重为 `69/6/4/3/2/2/1×14`。这是执行模型，不是论文实测比例。

### 测试阶段

默认 6 个阶段，总正式测试时间 10 分钟：3 个 dataset 阶段各 160 秒，3 个 checkpoint 阶段各 40 秒。

| 阶段 | 读/写 | 访问数据 | 目的 |
|---|---|---|---|
| `dataset_epoch_01` | 读 | 全部 `dataset_rank` | rank 01 最高权重，模拟首轮训练数据热点 |
| `dataset_epoch_02` | 读 | 全部 `dataset_rank` | rank 02 最高权重，模拟训练数据热点迁移 |
| `dataset_epoch_03` | 读 | 全部 `dataset_rank` | rank 03 最高权重，继续制造时序变化 |
| `checkpoint_read_current_first` | 读 | `checkpoint_current` | 首次加载当前 checkpoint |
| `checkpoint_read_current_second` | 读 | `checkpoint_current` | 短期重复读取并复热 |
| `recovery_read_old_checkpoint` | 读 | `checkpoint_old` | 旧 checkpoint 复热 |

每个 dataset 阶段都会访问全部 20 个 rank，只是访问权重不同。checkpoint 阶段保留 MLPerf Storage/DLIO 的加载和恢复语义，但正式测试只读取造数据阶段生成的文件，以避免单盘写瓶颈破坏固定 IOPS。

### 适用范围与限制

- 不运行真实模型训练。
- 不评价 GPU/训练吞吐。
- 论文和 MLPerf 提供读写语义，但没有给出可直接落地的热数据容量占比和访问占比。
- Zipfian 权重和容量缩放是当前单节点实验参数，后续可由公开 trace 提取结果替换。

## 5. AI 推理：LLM KV cache 负载

### 来源

- vLLM/PagedAttention：`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023（CCF-A）。
- MLPerf Storage KV Cache benchmark 类别。

### 设计逻辑

LLM 推理中，prefill 会生成 KV cache，decode 阶段会持续读取已有 KV cache。当前单盘缩放模型在造数据阶段生成 KV 文件，正式测试只执行读取、热点迁移和复热，并用 Zipfian rank 表达偏斜访问。

数据构造上，active/next/prefix 三类 KV cache 各约 39.06 GiB，每类包含 20 个 rank，每个 rank 为 100 个 20 MiB 文件。按 4 MiB object 估算，每类 KV cache 约为 10000 个 object。先按 object 级 Zipf(alpha=0.99) 计算访问概率，再聚合到每类 20 个等容量 rank，得到 `68/7/4/3/2/2/1×14`。三类 KV cache 分别对应当前会话、下一批会话和可复用 prefix。

### 测试数据分布

| 数据池 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `kv_active_rank`<br>`_01~20` | 20 × 100 | 20 MiB | 约 39.06 GiB | 当前请求/会话 KV cache |
| `kv_next_rank`<br>`_01~20` | 20 × 100 | 20 MiB | 约 39.06 GiB | 下一批请求 KV cache |
| `kv_prefix_rank`<br>`_01~20` | 20 × 100 | 20 MiB | 约 39.06 GiB | 可复用 prefix KV cache |

每类 KV cache 都按 20 个等容量 rank 切分。相关阶段按 4 MiB object 计算 Zipf(alpha=0.99)，再聚合到 20 个 rank，整数化权重为 `68/7/4/3/2/2/1×14`。

### 测试阶段

默认 6 个阶段各 100 秒，总正式测试时间 10 分钟。

| 阶段 | 读/写 | 访问数据 | 目的 |
|---|---|---|---|
| `prefill_active` | 读 | 全部 `kv_active_rank` | 读取当前请求的预生成 KV cache |
| `decode_active` | 读 | 全部 `kv_active_rank` | decode 持续读取当前 KV cache |
| `prefill_next` | 读 | 全部 `kv_next_rank` | 读取下一批预生成 KV cache，`kv_next_rank_01` 为最高权重热点 |
| `decode_next` | 读 | 全部 `kv_next_rank` | decode 读取新 KV cache，`kv_next_rank_01` 保持最高权重热点 |
| `prefix_reuse_primary` | 读 | 全部 `kv_prefix_rank` | 共享前缀/多轮对话复用旧 KV cache |
| `prefix_reuse_shifted` | 读 | 全部 `kv_prefix_rank` | prefix 内部热点 rank 旋转 |

prefill 阶段使用顺序读；decode 和 prefix reuse 阶段使用随机读。所有阶段统一使用 4 MiB 请求，所有数据池都会在正式测试阶段被访问。

### 适用范围与限制

- 不运行真实 LLM。
- 不评价 token 生成速度。
- 正式测试不复现 KV cache 持久化写入，只保留预生成数据的读取热度变化。
- PagedAttention 支撑 KV cache 行为模型，但没有给出热 KV cache 的固定容量/访问比例。
- Zipfian 权重和容量缩放是当前单节点实验参数，后续可由公开 trace 提取结果替换。
