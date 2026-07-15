# 单节点冷热识别负载

本目录包含 5 个正式 Vdbench 负载和 1 个保留的 HPC IOR 负载。目标是以来源
可追溯的应用生命周期为框架，在 CephFS 上制造可重复的文件级冷热变化；它们
不是原生应用性能 benchmark。

## 统一数据与 I/O 规则

- 每个正式 Vdbench 负载固定 2,400 个逻辑单元，共 112.5 GiB；
- 每个单元包含 `4 × 4 MiB + 2 × 8 MiB + 1 × 16 MiB = 48 MiB`；
- 同一逻辑组的每个固定大小档独立计算 Zipf(0.99)，再聚合到等容量 rank；
- rank 内 `fileselect=random`，文件内部由应用阶段选择顺序读或随机读；
- 正式阶段均为只读、`xfersize=4m`、Direct I/O、`fwdrate=max`；
- 阶段边界直接切换热点，不设置 `25/50/75%` 中间渐变态；
- prepare 每批最多处理 20 个 rank，造数据与正式测试完全分离。
- 正式 run 的 RD 使用与阶段同名的 `fwd=<阶段名>*` 前缀通配符；这样既保持
  原 FWD/skew 集合不变，也避免 Vdbench 5.04.07 的单个 RD 显式 FWD 列表上限。

Zipf(0.99) 是采用 YCSB 常用偏斜参数的受控执行模型，不是五类应用论文给出的
实测文件热度比例。所有文件都有非零理论概率，但有限测试时长不保证每个长尾
文件一定实际命中。

## 正式负载

| 类别 | 目录 | 数据结构 | 正式阶段 |
|---|---|---|---|
| 大数据 | `bigdata_mapreduce_vdbench_v1` | 4 个 pool；24 rank/pool | 4 × 150 s |
| 图计算 | `graph_graphchi_vdbench_v1` | 4 shard × 100 rank | 4 × 150 s |
| HPC | `hpc_wrf_vdbench_v1` | 3 组 × 80 rank | 4 × 150 s |
| AI 训练 | `ai_training_checkpoint_vdbench_v1` | dataset/current/old × 100 rank | 3 × 160 s + 2 × 60 s |
| AI 推理 | `ai_inference_kvcache_vdbench_v1` | active/next/prefix × 80 rank | 6 × 100 s |

每行阶段总时长均为 600 秒。每个阶段只生成一个 RD；热点在相邻 RD 之间直接
切换，便于按明确时间边界评估冷热识别。

`hpc_wrf_ior_v1` 保留 WRF 的 MPI、file-per-process 和并行 I/O 语义，不应用
混合文件大小或 Zipf rank。它同样为 112.5 GiB，并使用 4 MiB 传输；HPC
Vdbench 与 HPC IOR 是同一容量预算下的两种替代表示，不要求同时保留。若六套
数据都保留，逻辑容量为 675 GiB，必须另行预留 Ceph 和 SSD 空闲空间。12 节点、
三副本、每负载 750 GiB 的版本位于
[`../SYSU_workload`](../SYSU_workload/README.md)。

来源、阶段和适用范围见 [WORKLOAD_SUMMARY.md](WORKLOAD_SUMMARY.md)，详细参数
见各负载目录的 `README.md` 与 `SOURCES.md`。四份项目场景需求报告与当前
冷热模型的对应关系、差异和工具选型见
[STORAGE_SCENE_PDF_ANALYSIS.md](STORAGE_SCENE_PDF_ANALYSIS.md)。

## 使用方式

每个正式负载目录均提供：

- `render_config.sh`：生成 `rendered/prepare_data.vdb` 和 `run_test.vdb`；
- `validate_model.sh`：验证容量、rank、Zipf 权重和阶段结构；
- `prepare_data.sh`：清理并创建数据；
- `run_test.sh`：只执行正式测试，不重新造数据。

修改模型或生成器后，应从仓库根目录执行统一验收：

```bash
./new_workload/validate_all.sh
```

该入口会重新渲染五个正式 Vdbench 负载，执行共享模型测试、全部 shell 语法检查、
单节点 IOR 验证，并用 Vdbench 5.04.07 的 `-s -e 2` 模式实际解析 10 份 prepare/run
配置。可用 `VDBENCH_BIN=/path/to/vdbench` 覆盖默认工具路径。

统一验证器还会展开每个通配符，要求单个正式 RD 实际匹配的 FWD 不超过 512；
当前单节点最大 300，SYSU 最大 500。

首次运行依次执行 validate、prepare、run；数据准备完成后只重复 run。默认数据
根目录为 `/mnt/cephfs`，也可通过 `ANCHOR_ROOT` 覆盖。单节点 `hd=` 参数由
`HOST1`、`REMOTE_USER` 和 `VDBENCH_HOME` 生成。

本次布局已从旧版单一文件大小/少量 rank 改为新的混合大小目录结构；已有旧版
数据不能复用，首次切换时必须重新执行 prepare，并确认旧目录已清理。

`bigdata_fixed_hot_vdbench_v1` 与 `graph_graphchi_fixed_hot_vdbench_v1` 是保留的
旧诊断实验，不属于当前五个正式模型，也没有随本次布局同步更新。
