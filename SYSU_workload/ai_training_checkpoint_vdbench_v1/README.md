# SYSU AI 训练 Vdbench 冷热负载

这是 12 节点、三副本环境使用的 750 GiB 版本。它不运行真实模型训练，
而是用 Vdbench 表达训练数据重复读取、热点迁移、当前 checkpoint 重读和旧
checkpoint 恢复。

## 来源与边界

训练数据语义来自 Meta DSI 的大规模深度推荐训练存储分析（ISCA 2022，
CCF-A）；checkpoint 语义参考 MLPerf Storage/DLIO。详细映射见
[`../../new_workload/ai_training_checkpoint_vdbench_v1/SOURCES.md`](../../new_workload/ai_training_checkpoint_vdbench_v1/SOURCES.md)。

来源支持训练数据反复读取、访问偏斜以及 checkpoint 加载/恢复，但没有给出
可直接落到 CephFS 的热容量与访问比例。Zipf(0.99)、容量、rank 数和阶段时长
都是冷热识别执行模型。正式阶段为纯读，checkpoint 只在造数据阶段写入。

## 数据构造

| 数据组 | 容量 | 结构 | 文件数 |
|---|---:|---|---:|
| `dataset` | 650 GiB | 20 × 32.5 GiB rank | 64,480 |
| `checkpoint_current` | 50 GiB | 1 个状态组 | 4,960 |
| `checkpoint_old` | 50 GiB | 1 个状态组 | 4,960 |
| 合计 | 750 GiB | — | 74,400 |

每个 dataset rank 使用 104 个容量单元，共 3,224 个文件：

| 文件大小 | 每 rank 文件数 | 每 rank 容量 |
|---:|---:|---:|
| 4 MiB | 1,664 | 6.5 GiB |
| 8 MiB | 832 | 6.5 GiB |
| 16 MiB | 416 | 6.5 GiB |
| 32 MiB | 208 | 6.5 GiB |
| 64 MiB | 104 | 6.5 GiB |

每个 checkpoint 使用 160 个容量单元，五档文件各占 10 GiB。

## Dataset 阶段内冷热

650 GiB dataset 按 4 MiB 等价对象计算为 166,400 个对象。对象级
Zipf(alpha=0.99) 聚合到 20 个等容量 rank 后，整数权重为：

```text
74 / 5 / 3 / 2 / 1 × 16
```

最热 rank 为 32.5 GiB，占 dataset 容量 5%、占总容量约 4.33%，承担
dataset 阶段 74% 操作。全部 20 个 rank 都有非零访问。三个 epoch 依次把
最高权重旋转到 rank 01、02、03。

## 正式阶段

| 阶段 | 时长 | 访问数据 | I/O 模式 | 最高热点 |
|---|---:|---|---|---|
| `dataset_epoch_01` | 160 s | 全部 dataset rank | 随机读 | rank 01 |
| `dataset_epoch_02` | 160 s | 全部 dataset rank | 随机读 | rank 02 |
| `dataset_epoch_03` | 160 s | 全部 dataset rank | 随机读 | rank 03 |
| `checkpoint_read_current_first` | 40 s | current checkpoint | 顺序读 | 整个 current 组 |
| `checkpoint_read_current_second` | 40 s | current checkpoint | 顺序读 | current 复热 |
| `recovery_read_old_checkpoint` | 40 s | old checkpoint | 顺序读 | old 复热 |

总 I/O 时间为 `160 × 3 + 40 × 3 = 600` 秒。checkpoint 阶段不使用 Zipf，
50 GiB 组内五档文件各承担 20% 操作。所有正式请求均为 4 MiB Direct I/O；
默认 `THREADS=1`、`FWD_RATE=max`。

## 使用

```bash
cd /home/chris/ceph-test/SYSU_workload/ai_training_checkpoint_vdbench_v1
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据目录为 `$ANCHOR_ROOT/ai_training_checkpoint_vdbench_v1`。当前配置没有
`hd=`。

## 适用范围

- 用于训练数据热点迁移和 checkpoint 复热识别。
- 不运行模型，不评价 GPU、训练吞吐或 MLPerf 成绩。
- epoch 热点旋转和 Zipf 权重不是 Meta DSI trace 的实测比例。
- 正式测试不模拟 checkpoint 写入开销。
