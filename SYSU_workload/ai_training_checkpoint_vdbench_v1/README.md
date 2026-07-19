# SYSU AI 训练数据与 checkpoint 负载

这是单节点 AI 训练模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/ai_training_checkpoint_vdbench_v1/README.md`](../../new_workload/ai_training_checkpoint_vdbench_v1/README.md)。

| 数据组 | 单元 | 容量 | 参考 rank | 物理 bin |
|---|---:|---:|---:|---:|
| `dataset` | 2,000 | 625 GiB | 100 | 40 |
| `checkpoint_current` | 200 | 62.5 GiB | 100 | 40 |
| `checkpoint_old` | 200 | 62.5 GiB | 100 | 40 |

三个 dataset epoch 各随机读 160 秒，Zipf 头依次为 rank 1、2、3；随后
current checkpoint 与 old checkpoint 各顺序读 60 秒。各边界直接切换。
三个数据组的每个固定大小档均先计算100个参考rank的Zipf(0.99)，再按前20个
单独保留、后80个每4个合并压缩为40个bin。dataset头部/尾部bin为6.25/25 GiB，
checkpoint为0.625/2.5 GiB。每阶段200 FWD，总时长600秒。

数据目录为 `$ANCHOR_ROOT/ai_training_checkpoint_vdbench_v1`；配置不含 `hd=`。
