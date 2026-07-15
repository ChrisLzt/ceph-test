# SYSU AI 训练数据与 checkpoint 负载

这是单节点 AI 训练模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/ai_training_checkpoint_vdbench_v1/README.md`](../../new_workload/ai_training_checkpoint_vdbench_v1/README.md)。

| 数据组 | 单元 | 容量 | rank | 每 rank 容量 |
|---|---:|---:|---:|---:|
| `dataset` | 2,000 | 625 GiB | 100 | 6.25 GiB |
| `checkpoint_current` | 200 | 62.5 GiB | 100 | 0.625 GiB |
| `checkpoint_old` | 200 | 62.5 GiB | 100 | 0.625 GiB |

三个 dataset epoch 各随机读 160 秒，Zipf 头依次为 rank 1、2、3；随后
current checkpoint 与 old checkpoint 各顺序读 60 秒。各边界直接切换。
三个数据组的每个固定大小档均独立计算 Zipf(0.99)，总时长为
`160 × 3 + 60 × 2 = 600` 秒。全部为 4 MiB Direct I/O、`fwdrate=max`。

数据目录为 `$ANCHOR_ROOT/ai_training_checkpoint_vdbench_v1`；配置不含 `hd=`。
