# 单节点冷热识别负载

本目录保存单节点 CephFS 冷热识别负载。目标不是复现原生应用性能，也不是
提交标准 benchmark 成绩，而是在来源可追溯的前提下，用通用 I/O 工具产生
可观察、可重复的冷热变化。

这里共有 **5 类负载、6 个可执行实现**：大数据、图计算、HPC、AI 训练和
AI 推理是 5 类应用；HPC 同时提供 Vdbench 与 IOR 两种实现。12 节点、三副本、
750 GiB 版本位于 [`../SYSU_workload`](../SYSU_workload/README.md)，两套配置和
数据目录互不覆盖。

更精简的来源与模型说明见 [WORKLOAD_SUMMARY.md](WORKLOAD_SUMMARY.md)。

## 正式负载

| 类别 | 实现 | 工具 | 逻辑容量 | 正式阶段 |
|---|---|---|---:|---|
| 大数据 | [MapReduce](bigdata_mapreduce_vdbench_v1/README.md) | Vdbench | 117.19 GiB | 4 × 150 s |
| 图计算 | [GraphChi](graph_graphchi_vdbench_v1/README.md) | Vdbench | 112.50 GiB | 5 × 120 s |
| HPC | [WRF 生命周期](hpc_wrf_vdbench_v1/README.md) | Vdbench | 112.50 GiB | 4 × 150 s |
| HPC 备选 | [WRF 并行 I/O](hpc_wrf_ior_v1/README.md) | IOR | 108.00 GiB | 4 × 150 s |
| AI 训练 | [数据读取与 checkpoint](ai_training_checkpoint_vdbench_v1/README.md) | Vdbench | 113.28 GiB | 3 × 160 s + 3 × 40 s |
| AI 推理 | [KV cache](ai_inference_kvcache_vdbench_v1/README.md) | Vdbench | 117.19 GiB | 6 × 100 s |

默认五类集合选用 HPC Vdbench 实现，总逻辑容量约 572.66 GiB。IOR 是 HPC 的
替代实现，不与 Vdbench 版本同时计入五类容量。

所有正式测试阶段均为只读；写入和目录重建只发生在 `prepare_data.sh`。这样做
是为了让单节点实验重点观察冷热识别，不能据此声称完整复现了应用原本的写入
行为。

## 来源与实验参数的边界

- 论文或官方文档决定应用语义，例如 MapReduce temporal locality、GraphChi
  PSW、WRF 文件生命周期、训练数据读取/checkpoint 和 KV cache 生命周期。
- 容量缩放、阶段时长、Vdbench/IOR 参数以及 Zipf 权重属于受控实验设计，除非
  分负载文档明确标注为论文观测值。
- HPC Vdbench、AI 训练和 AI 推理使用 Zipf(0.99) 表达长尾访问。该参数采用
  YCSB 常见设定，但不是 WRF、Meta DSI 或 PagedAttention 的实测冷热比例。
- GraphChi 的 `75/13/6/6` 来自当前 generated graph 和 PSW 推导流程；它不是
  GraphChi 论文规定的通用固定比例。
- AI 比例未来可由公开或目标系统 trace 替换，方案见
  [AI_TRACE_RATIO_PLAN.md](AI_TRACE_RATIO_PLAN.md)。

## 阶段概览

### 大数据

```text
hot_a -> hot_b -> hot_c -> reheat_a
```

`pool_01~03` 轮流承担 85% 访问，`pool_04` 始终承担 13% 背景访问。所有池都
会被访问，不再保留全程 0 访问的 inactive 池。

### 图计算

```text
iter1_i0 -> iter1_i1 -> iter1_i2 -> iter1_i3 -> iter2_i0
```

前四阶段完成一轮 interval 处理，最后一阶段让 `shard_00` 复热。每阶段都读取
全部四个 shard，只是由当前 memory-shard 承担主要访问。

### HPC

```text
startup_read -> checkpoint_read -> history_read -> checkpoint_reheat
```

Vdbench 版本在每个活动组内部使用 20 个等容量 rank 和 Zipf 权重，形成明确的
阶段内冷热；IOR 版本保留 4 个 MPI rank 与 file-per-process 语义，但只表达组间
生命周期，不提供组内 Zipf。

### AI 训练

```text
dataset_epoch_01 -> dataset_epoch_02 -> dataset_epoch_03
-> checkpoint_read_current_first
-> checkpoint_read_current_second
-> recovery_read_old_checkpoint
```

三个 dataset 阶段轮换最高权重 rank；随后两次读取当前 checkpoint，再读取旧
checkpoint。正式阶段不会写 checkpoint。

### AI 推理

```text
prefill_active -> decode_active
-> prefill_next -> decode_next
-> prefix_reuse_primary -> prefix_reuse_shifted
```

prefill 使用顺序读，decode 与 prefix reuse 使用随机读。热点先从 active 迁移到
next，最后进入 prefix 数据组并在组内旋转。

## 统一工作流

每个正式负载目录均提供：

- `README.md`：来源、数据布局、阶段和适用范围；
- `SOURCES.md`：文献与参数映射；
- `validate_model.sh`：检查模型、容量和配置结构；
- `prepare_data.sh`：清理并创建数据；
- `run_test.sh`：只运行正式测试。

基本流程：

```bash
cd /home/chris/ceph-test/new_workload/<负载目录>
./validate_model.sh
./prepare_data.sh
./run_test.sh
```

数据已准备好后只需重复执行：

```bash
./run_test.sh
```

不要在每次测试前重复执行 `prepare_data.sh`，否则会重建文件并重置对象历史。

单节点正式 Vdbench 负载默认 `fwdrate=1000`，用于维持阶段访问比例；如需测试
冷热识别模块的最大吞吐开销，可显式设置 `FWD_RATE=max`。IOR 不使用
`fwdrate` 参数。

## 诊断负载

- [bigdata_fixed_hot_vdbench_v1](bigdata_fixed_hot_vdbench_v1/README.md)
- [graph_graphchi_fixed_hot_vdbench_v1](graph_graphchi_fixed_hot_vdbench_v1/README.md)

这两个目录复用正式负载的数据，只用于排查固定热点与热点迁移的差异，不计入
5 类正式负载。它们保留了早期诊断参数，I/O 大小、阶段数或 `fwdrate` 不一定
与当前主负载相同；只有在参数对齐后才能作为严格的性能对照。
