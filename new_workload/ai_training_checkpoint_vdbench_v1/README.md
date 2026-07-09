# AI 训练 checkpoint vdbench Zipfian 冷热识别负载 v1

这个负载不运行真实模型训练，也不评价 GPU/训练吞吐。它把论文和官方 benchmark 中明确描述的 AI 训练存储行为，映射成 vdbench 对 CephFS 的阶段化读写，用于观察冷热识别：

- 训练数据被反复读取、过滤、复用；
- 训练数据访问存在偏斜，使用 Zipfian rank 表达“少量 rank 更频繁访问，但所有 rank 都会被访问”；
- checkpoint 被周期性写入；
- 新写入 checkpoint 会被读取或校验；
- 旧 checkpoint 在恢复阶段被重新读取。

## 来源

主来源：

- Meta DSI / ISCA 2022：`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`。该文描述大规模训练的数据存储与 ingestion pipeline，训练任务会持续读取、过滤大规模数据集，并存在跨训练任务的热门 features/samples。
- MLPerf Storage checkpointing / DLIO：MLPerf Storage 使用 DLIO 模拟 ML 训练存储 I/O，其中 checkpointing workload 覆盖 checkpoint 写入、读取和恢复语义。

本目录使用 vdbench 执行这些读写阶段。vdbench 不是负载来源，只是把设定好的文件读写模型落到 CephFS 上。Zipfian 是当前实验用来表达访问偏斜的执行模型，不声明为论文给出的固定比例。

详细映射见 [SOURCES.md](SOURCES.md)。

## 默认数据路径和容量

默认数据路径：

```text
/mnt/cephfs/ai_training_checkpoint_vdbench_v1/
```

默认容量约为 113.28 GiB：

| 数据集 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `dataset_rank_01~20` | 20 × 250 | 20 MiB | 约 97.66 GiB | 训练数据 rank，正式阶段全部参与 Zipfian 读取 |
| `checkpoint_current` | 400 | 20 MiB | 约 7.81 GiB | 当前 checkpoint，先写后读 |
| `checkpoint_old` | 400 | 20 MiB | 约 7.81 GiB | 旧 checkpoint，恢复阶段复热 |

### 数据构造由来

`dataset_rank_01~20` 表示训练数据集被切成 20 个等容量 rank。这样做的目的不是模拟真实文件名，而是让 vdbench 能对同一类训练数据施加可控访问偏斜。每个 rank 有 250 个 20 MiB 文件，容量约 4.88 GiB；按 4 MiB object 估算，每个 rank 可看作 1250 个 object，20 个 rank 合计 25000 个 object。

训练数据访问偏斜采用 Zipf(alpha=0.99)。alpha=0.99 是 YCSB 常用 Zipfian 参数，表达“少量对象访问更多，但长尾对象仍会被访问”。脚本先按 25000 个 4 MiB object 计算 Zipf(0.99)，再聚合到 20 个等容量 rank。聚合后的 rank 访问占比约为 `70.9% / 6.7% / 3.9% / 2.8% / 2.2% / 1.8% / 1.5% ...`，vdbench 中整数化为 `69/6/4/3/2/2/1×14`。

`checkpoint_current` 和 `checkpoint_old` 是训练状态文件，不参与 Zipfian 训练样本分布。每组 400 个 20 MiB 文件，容量约 7.81 GiB，是当前单节点 100～120 GiB 测试预算下的缩放值，用于保留 checkpoint 写入、近期读取和旧 checkpoint 恢复这三个状态文件行为。

这个容量和权重不是 Meta DSI 或 MLPerf 给出的实测热数据比例；它是用 Meta DSI 的“训练数据反复读取且存在访问偏斜”语义，结合 YCSB Zipfian 分布构造的冷热识别执行模型。

## 工作流

```bash
cd /home/chris/ceph-test/new_workload/ai_training_checkpoint_vdbench_v1

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

默认 6 个阶段，总正式测试时间 10 分钟。dataset 阶段占 80% 时间，checkpoint 阶段占 20% 时间。

```text
dataset_epoch_01
-> dataset_epoch_02
-> dataset_epoch_03
-> checkpoint_write_current
-> checkpoint_read_current
-> recovery_read_old_checkpoint
```

| 阶段 | 读/写 | 访问数据 | 目的 |
|---|---|---|---|
| `dataset_epoch_01` | 读 | 全部 `dataset_rank_01~20` | 160s；rank 01 为最高权重，模拟首轮训练数据热点 |
| `dataset_epoch_02` | 读 | 全部 `dataset_rank_01~20` | 160s；Zipfian 权重旋转到 rank 02，模拟热点迁移 |
| `dataset_epoch_03` | 读 | 全部 `dataset_rank_01~20` | 160s；Zipfian 权重旋转到 rank 03，继续制造时序变化 |
| `checkpoint_write_current` | 写 | `checkpoint_current` | 40s；模拟训练过程写出当前 checkpoint |
| `checkpoint_read_current` | 读 | `checkpoint_current` | 40s；模拟 checkpoint 写后校验、加载或近期恢复读取 |
| `recovery_read_old_checkpoint` | 读 | `checkpoint_old` | 40s；模拟从旧 checkpoint 恢复，旧状态文件复热 |

### 阶段由来

`dataset_epoch_01~03` 来自 Meta DSI 对训练数据 ingestion 的描述：训练任务会持续读取和过滤大规模数据集，并且部分 features/samples 更热门。这里用 3 个 epoch 阶段表达“训练数据反复被读”，同时旋转最高权重 rank，制造可观察的热点迁移，而不是让同一个目录永远最热。

`checkpoint_write_current`、`checkpoint_read_current`、`recovery_read_old_checkpoint` 来自 MLPerf Storage checkpointing / DLIO 的 checkpoint 语义：训练过程会写 checkpoint，后续可能读取当前 checkpoint 做校验、加载或近期恢复，也可能从旧 checkpoint 恢复。checkpoint 阶段保持顺序读写，因为 checkpoint 是训练状态文件，不是样本级随机访问分布。

数据读取阶段的访问比例来自 Zipfian 权重，不再设置“完全不访问”的训练数据池。6 个阶段总时长固定为 600 秒，其中 dataset 读占 480 秒，checkpoint 生命周期占 120 秒；这样既保留 checkpoint 行为，又避免短事件阶段吞掉主要训练数据热度。

## 可调参数

```bash
ANCHOR=/mnt/cephfs/ai_training_checkpoint_vdbench_v1 THREADS=8 FORMAT_THREADS=4 DATASET_PHASE_SECONDS=160 CHECKPOINT_PHASE_SECONDS=40 FWD_RATE=max READ_XFER_SIZE=1m CHECKPOINT_XFER_SIZE=4m ./render_config.sh all
```

默认 `THREADS=8`，允许多线程。单节点 SN350 上如果 Ceph 出现 backfill、recovery 或 slow ops，应先停止测试，等 `ceph -s` 恢复 `active+clean` 后再运行。

## 适用范围

- 这不是正式 MLPerf Storage 结果。
- 这不是训练性能 benchmark。
- 论文和官方 benchmark 提供读写语义；vdbench 的 `xfersize`、线程数、容量缩放是当前实验环境参数。
- Zipf(alpha=0.99) 采用 YCSB 常用参数；这里按 4 MiB object 计算后聚合到 vdbench rank，不是 Meta DSI 或 MLPerf 给出的实测热数据容量/访问比例。
