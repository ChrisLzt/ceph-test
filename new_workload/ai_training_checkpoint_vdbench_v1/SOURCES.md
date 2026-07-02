# AI 训练负载来源与映射

## 1. Meta DSI / ISCA 2022

论文：

- Mark Zhao 等，`Understanding Data Storage and Ingestion for Large-Scale Deep Recommendation Model Training`，ISCA 2022。
- arXiv: <https://arxiv.org/abs/2108.09373>

采用的负载逻辑：

- 大规模训练依赖数据存储和 ingestion pipeline；
- 训练任务持续读取、过滤大规模训练数据；
- 不同训练任务之间存在热门 features/samples；
- 因此训练数据侧应体现“部分数据被持续读取，部分数据较少读取或不读取”。

映射到本负载：

| 论文/系统现象 | vdbench 映射 |
|---|---|
| 训练反复读取数据集 | `epoch_read_hot_dataset` / `epoch_read_warm_dataset` |
| 热门 features/samples 被更频繁使用 | `dataset_hot` 被单独作为热点阶段读取 |
| 大规模数据中存在未被当前训练阶段访问的数据 | `dataset_cold` 只造数据，不在 run 阶段访问 |

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

## 3. 为什么使用 vdbench

当前目标是冷热识别，不是提交 MLPerf 成绩。vdbench 能稳定地在 CephFS 上创建固定容量文件，并按阶段执行读写，因此适合将上述来源中的负载语义简化为可控冷热模型。

需要明确的边界：

- 目录名不再使用 `mlperf`，因为这里不运行官方 MLPerf Storage closed/open 流程；
- `THREADS`、`xfersize`、容量缩放是执行参数，不是论文参数；
- Meta DSI 论文说明存在热门 features/samples 和训练数据反复读取，但没有给出“热数据占总容量 X%、承担总访问 Y%”这种可直接落地的固定比例；
- MLPerf Storage checkpointing 给出 checkpoint 写/读次数、模型配置、数据集/内存约束等 benchmark 参数，但它不是冷热分布论文，也没有给出 hot/cold 容量比例；
- 热/冷判断由测试者根据阶段语义和 Ceph 观测结果自行判断，不在脚本中生成真值表。
