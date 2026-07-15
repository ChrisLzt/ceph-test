# AI 训练数据与 checkpoint 冷热负载

## 来源与设计逻辑

训练数据语义来自 Meta DSI 的 *Understanding Data Storage and Ingestion for
Large-Scale Deep Recommendation Model Training*（ISCA 2022，CCF-A）；
checkpoint 加载与恢复语义参考 MLPerf Storage/DLIO。来源支持训练数据重复
读取、访问偏斜和 checkpoint 生命周期，但没有给出可直接套用的文件级冷热
比例。Zipf(0.99) 因此是明确标注的受控参数，详见 [SOURCES.md](SOURCES.md)。

## 数据构造

| 数据组 | 单元 | 容量 | rank | 每 rank 单元/容量 |
|---|---:|---:|---:|---:|
| `dataset` | 2,000 | 93.75 GiB | 100 | 20 / 960 MiB |
| `checkpoint_current` | 200 | 9.375 GiB | 100 | 2 / 96 MiB |
| `checkpoint_old` | 200 | 9.375 GiB | 100 | 2 / 96 MiB |

容量比例为 `10:1:1`。dataset rank 每档分别包含 80 个 4 MiB、40 个 8 MiB、
20 个 16 MiB 文件；checkpoint rank 分别为 8、4、2 个。三个数据组的每个
固定大小档都独立计算 Zipf(0.99)，checkpoint 不再作为组内完全均匀的大文件。

## 正式阶段

| 阶段 | 数据 | 模式 | Zipf 头 | 时长 |
|---|---|---|---:|---:|
| `dataset_epoch_01` | dataset | 随机读 | rank 1 | 160 s |
| `dataset_epoch_02` | dataset | 随机读 | rank 2 | 160 s |
| `dataset_epoch_03` | dataset | 随机读 | rank 3 | 160 s |
| `checkpoint_read_current` | current | 顺序读 | rank 1 | 60 s |
| `recovery_read_old_checkpoint` | old | 顺序读 | rank 1 | 60 s |

前三个 epoch 使用同一 dataset，但 Zipf 排名分别旋转，使 rank 1、rank 2、
rank 3 依次成为最热 rank；其余 rank 仍有非零理论访问概率。阶段边界直接
切换，不生成中间渐变态。总时长为 `160 × 3 + 60 × 2 = 600` 秒。全部请求为
4 MiB Direct I/O、`fwdrate=max`。

## 适用范围

适合观察训练数据热点迁移、当前 checkpoint 重读和旧 checkpoint 恢复；不运行
模型、不评价 GPU/训练吞吐，也不是 MLPerf 提交结果。正式阶段只读取预生成
checkpoint，不模拟写入开销。

数据默认位于 `/mnt/cephfs/ai_training_checkpoint_vdbench_v1`。
