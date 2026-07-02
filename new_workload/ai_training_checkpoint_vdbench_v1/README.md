# AI 训练 checkpoint vdbench 冷热识别负载 v1

这个负载不运行真实模型训练，也不评价 GPU/训练吞吐。它把论文和官方 benchmark 中明确描述的 AI 训练存储行为，映射成 vdbench 对 CephFS 的读写阶段，用于观察冷热识别：

- 训练数据被多次读取、过滤、复用；
- checkpoint 被周期性写入；
- 新写入 checkpoint 会被读取或校验；
- 旧 checkpoint 在恢复阶段被重新读取；
- 冷数据长期不访问，作为对照。

## 来源

主来源：

- Meta DSI / ISCA 2022：`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`。该文描述大规模训练的数据存储与 ingestion pipeline，训练任务会持续读取、过滤大规模数据集，并存在跨训练任务的热门 features/samples。
- MLPerf Storage checkpointing / DLIO：MLPerf Storage 使用 DLIO 模拟 ML 训练存储 I/O，其中 checkpointing workload 覆盖 checkpoint 写入、读取和恢复语义。

本目录使用 vdbench 执行这些读写阶段。vdbench 不是负载来源，只是把设定好的文件读写模型落到 CephFS 上。

详细映射见 [SOURCES.md](SOURCES.md)。

## 默认数据路径和容量

默认数据路径：

```text
/mnt/cephfs/ai_training_checkpoint_vdbench_v1/
```

默认容量为 112 GiB：

| 数据集 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `dataset_hot` | 32 | 1 GiB | 32 GiB | 训练 epoch 中反复读取的热门训练数据 |
| `dataset_warm` | 24 | 1 GiB | 24 GiB | 被读取但热度较低的训练数据 |
| `dataset_cold` | 32 | 1 GiB | 32 GiB | 不在测试阶段访问的冷训练数据 |
| `checkpoint_current` | 12 | 1 GiB | 12 GiB | 当前 checkpoint，写后读 |
| `checkpoint_old` | 12 | 1 GiB | 12 GiB | 旧 checkpoint，恢复阶段复热 |

这些容量是当前单节点 CephFS 100–120 GiB/负载预算下的缩放值，不声称来自论文的固定容量比例。

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

```text
epoch_read_hot_dataset
-> epoch_read_warm_dataset
-> checkpoint_write_current
-> checkpoint_read_current
-> recovery_read_old_checkpoint
```

- `epoch_read_hot_dataset`：模拟训练 epoch 中热门样本/features 所在数据被反复读取。
- `epoch_read_warm_dataset`：模拟同一训练周期中较低热度的数据读取。
- `checkpoint_write_current`：模拟训练过程写出当前 checkpoint。
- `checkpoint_read_current`：模拟 checkpoint 写后校验、加载或近期恢复读取。
- `recovery_read_old_checkpoint`：模拟从旧 checkpoint 恢复，旧数据复热。

`dataset_cold` 在测试阶段不读写，用于观察冷数据能否保持冷状态。

## 可调参数

```bash
ANCHOR=/mnt/cephfs/ai_training_checkpoint_vdbench_v1 \
THREADS=8 \
FORMAT_THREADS=4 \
PHASE_SECONDS=120 \
FWD_RATE=1000 \
READ_XFER_SIZE=1m \
CHECKPOINT_XFER_SIZE=4m \
./render_config.sh all
```

默认正式测试包含 5 个阶段，每阶段 `PHASE_SECONDS=120`，总时长约 10 分钟。默认 `THREADS=8`，允许多线程，但不会像旧 Python proxy 那样一次性并发写多个 7 GiB 大对象。单节点 SN350 上如果 Ceph 出现 backfill、recovery 或 slow ops，应先停止测试，等 `ceph -s` 恢复 `active+clean` 后再运行。

## 边界

- 这不是正式 MLPerf Storage 结果。
- 这不是训练性能 benchmark。
- 论文和官方 benchmark 提供读写语义；vdbench 的 `xfersize`、线程数、容量缩放是当前实验环境参数。
