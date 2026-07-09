# 冷热识别负载总览

本目录保存 5 类来源驱动的冷热识别测试负载。当前目标不是复现原生应用性能，而是在符合负载特性的前提下，用通用工具构造可观察、可重复的冷热变化。

更简要的来源与设计说明见 [WORKLOAD_SUMMARY.md](WORKLOAD_SUMMARY.md)。

## 当前状态

| 负载 | 子目录 | 来源 | 执行工具 | 默认容量 | 运行时数据路径 |
|---|---|---|---|---:|---|
| 大数据 | [bigdata_mapreduce_vdbench_v1](bigdata_mapreduce_vdbench_v1/README.md) | Yahoo Hadoop/MapReduce 生产 trace | vdbench | 约 117.19 GiB | `/mnt/cephfs/bigdata_mapreduce_vdbench_v1` |
| 图计算 | [graph_graphchi_vdbench_v1](graph_graphchi_vdbench_v1/README.md) | GraphChi OSDI 2012 PSW | vdbench | 约 112.50 GiB | `/mnt/cephfs/graph_graphchi_vdbench_v1` |
| HPC | [hpc_wrf_ior_v1](hpc_wrf_ior_v1/README.md) | WRF checkpoint/restart/history 语义 | IOR | 约 112.00 GiB | `/mnt/cephfs/hpc_wrf_ior_v1` |
| AI 训练 | [ai_training_checkpoint_vdbench_v1](ai_training_checkpoint_vdbench_v1/README.md) | Meta DSI ISCA 2022 + MLPerf Storage checkpointing | vdbench | 约 113.28 GiB | `/mnt/cephfs/ai_training_checkpoint_vdbench_v1` |
| AI 推理 | [ai_inference_kvcache_vdbench_v1](ai_inference_kvcache_vdbench_v1/README.md) | vLLM/PagedAttention SOSP 2023 + MLPerf Storage KV Cache | vdbench | 约 117.19 GiB | `/mnt/cephfs/ai_inference_kvcache_vdbench_v1` |

合计默认容量约 572.16 GiB，符合当前单节点 CephFS 约 600 GiB 测试预算。

`graph_graphchi_fixed_hot_vdbench_v1` 和 `bigdata_fixed_hot_vdbench_v1` 是诊断负载，不计入 5 类正式负载。它们复用已有数据，用于排查热点迁移、固定热点等单一因素，不作为默认测试集合。

## 目录约定

每个负载目录都应包含：

- `README.md`：来源、负载逻辑、执行方法和适用范围。
- `SOURCES.md`：文献/官方 benchmark 来源和参数映射。
- `validate_model.sh`：模型和脚本校验。
- `prepare_data.sh`：只造数据。
- `run_test.sh`：只跑正式测试。

## 统一工作流

每个负载目录都使用同一套入口：

```bash
cd /home/chris/ceph-test/new_workload/<负载目录>

./validate_model.sh
./prepare_data.sh
./run_test.sh
```

含义：

- `validate_model.sh`：检查模型、容量、脚本结构和当前渲染配置。
- `prepare_data.sh`：只造数据，会覆盖或重建该负载的数据集。
- `run_test.sh`：只跑正式冷热测试，不重新造全量数据。

数据已经准备好后，重复测试只运行：

```bash
./run_test.sh
```

不要在每次测试前重复运行 `prepare_data.sh`，否则会重置对象历史，影响冷热识别结果。

## 5 类负载的冷热逻辑

### 大数据

```text
hot_a -> hot_b -> hot_c -> reheat_a
```

- `pool_01/pool_02/pool_03` 轮流成为热点。
- `pool_04` 是活跃背景数据。
- 当前版本不再保留全程不访问的 `pool_05`；原 inactive/cold 容量已按论文原始比例分配给可访问数据池。

### 图计算

```text
iter1_i0 -> iter1_i1 -> iter1_i2 -> iter1_i3
-> iter2_i0 -> iter2_i1 -> iter2_i2 -> iter2_i3
```

- 当前 interval 对应 shard 是 memory-shard，成为热点。
- 热点随 GraphChi execution interval 迁移。
- 第二轮迭代让旧 shard 复热。
- `graph_graphchi_fixed_hot_vdbench_v1` 固定 `shard_00` 为热点，用于判断 accuracy 下降是否主要来自热点迁移。

### HPC

```text
startup read -> checkpoint write/read -> history write/read -> recovery read old checkpoint
```

- input/restart 启动阶段短期热。
- current checkpoint/history 写后读，成为热数据。
- old checkpoint 在 recovery 阶段复热。
- old history 不访问，作为冷数据对照。

### AI 训练

```text
dataset epoch reads
-> checkpoint write/read
-> recovery read old checkpoint
```

- `dataset_rank_01~20` 全部参与训练数据读取。
- 每个 dataset 阶段使用 Zipfian 权重，少量 rank 更热，但没有全程不访问的训练数据池。
- `checkpoint_current` 写后读，成为 checkpoint 热点。
- `checkpoint_old` 在 recovery 阶段复热。

### AI 推理

```text
prefill write current -> decode read current
-> prefill write next -> decode read next
-> prefix reuse read old
```

- `kv_active` 是当前会话 KV。
- `kv_next` 是下一批会话 KV，热点迁移。
- `kv_prefix_rank` 是 prefix reuse KV，支持旧 KV 复热。
- active/next/prefix 三类 KV 都按 rank 切分并使用 Zipfian 权重，没有全程不访问的 KV 数据池。
