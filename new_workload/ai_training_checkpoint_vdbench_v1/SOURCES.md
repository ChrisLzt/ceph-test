# AI 训练负载来源与映射

## 1. Meta DSI / ISCA 2022

论文：

- Mark Zhao 等，`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`，ISCA 2022。
- arXiv: <https://arxiv.org/abs/2108.09373>

采用的负载逻辑：

- 大规模训练依赖数据存储和 ingestion pipeline；
- 训练任务持续读取、过滤大规模训练数据；
- 不同训练任务之间存在热门 features/samples；
- 因此训练数据侧应体现“所有数据都有机会被访问，但访问频度存在偏斜”。

映射到本负载：

| 论文/系统现象 | vdbench 映射 |
|---|---|
| 训练反复读取数据集 | `dataset_epoch_01~03` |
| 热门 features/samples 被更频繁使用 | 对 `dataset_rank_01~20` 施加 Zipfian skew |
| 热点随训练阶段变化 | 每个 epoch 旋转 Zipfian rank 顺序 |

## 2. MLPerf Storage checkpointing / DLIO

官方来源：

- MLCommons Storage：<https://github.com/mlcommons/storage>
- DLIO：<https://github.com/argonne-lcf/dlio_benchmark>

采用的负载逻辑：

- MLPerf Storage 用 DLIO 模拟 ML 应用的存储 I/O；
- checkpointing workload 关注 checkpoint 写入、读取和恢复；
- 这类 I/O 是 AI 训练中区别于普通只读数据集扫描的重要存储行为。

映射到本负载：

| 官方 benchmark 语义 | vdbench 映射 |
|---|---|
| checkpoint write | `checkpoint_write_current` |
| checkpoint read / validation / reload | `checkpoint_read_current` |
| recovery from previous checkpoint | `recovery_read_old_checkpoint` |

## 3. 为什么使用 vdbench + Zipfian

当前目标是冷热识别，不是提交 MLPerf 成绩。vdbench 能稳定地在 CephFS 上创建固定容量文件，并按阶段执行读写；Zipfian skew 能表达“少量对象访问更多，但长尾对象仍然被访问”的偏斜访问。

需要明确的适用范围：

- 目录名不使用 `mlperf`，因为这里不运行官方 MLPerf Storage closed/open 流程；
- `THREADS`、`xfersize`、容量缩放是执行参数，不是论文参数；
- Meta DSI 论文说明存在热门 features/samples 和训练数据反复读取，但没有给出“热数据占总容量 X%、承担总访问 Y%”这种可直接落地的固定比例；
- 当前 Zipfian 权重采用 YCSB 常用 alpha=0.99。脚本按 4 MiB object 计算 Zipf(0.99)，再聚合到 20 个等容量 dataset rank，整数化为 `69/6/4/3/2/2/1×14`；后续可由公开 trace 提取结果替换；
- MLPerf Storage checkpointing 给出 checkpoint 写/读/恢复语义，但它不是冷热分布论文；
- 热/冷判断由测试者根据阶段语义和 Ceph 观测结果自行判断，不在脚本中生成真值表。
