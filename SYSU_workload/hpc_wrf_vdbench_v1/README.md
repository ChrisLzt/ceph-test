# SYSU WRF 生命周期 Vdbench 冷热负载

这是 12 节点、三副本环境使用的 750 GiB HPC 版本。它用 Vdbench 表达 WRF
类应用的 startup、checkpoint 和 history 文件生命周期，并在每个活动组内部
增加 Zipf(0.99) 长尾访问。

## 来源与边界

WRF 官方资料支持输入/边界、restart/checkpoint 和 history/output 文件语义。
详细映射见
[`../../new_workload/hpc_wrf_vdbench_v1/SOURCES.md`](../../new_workload/hpc_wrf_vdbench_v1/SOURCES.md)。

WRF 决定三个高层数据组及 checkpoint 复热语义；三组等容量、20 个逻辑 rank、
Zipf(0.99)、750 GiB 和阶段时长是冷热识别实验设计，不是 WRF trace 实测比例。

## 数据构造

| 数据组 | 容量 | 逻辑 rank | 文件数 | 作用 |
|---|---:|---:|---:|---|
| `startup` | 250 GiB | 20 | 24,800 | 输入和边界状态 |
| `checkpoint` | 250 GiB | 20 | 24,800 | 首次读取与复热 |
| `history` | 250 GiB | 20 | 24,800 | history/output 分析 |
| 合计 | 750 GiB | 60 | 74,400 | — |

每个逻辑 rank 为 12.5 GiB、1,240 个文件，使用 40 个容量单元：

| 文件大小 | 每 rank 文件数 | 每 rank 容量 |
|---:|---:|---:|
| 4 MiB | 640 | 2.5 GiB |
| 8 MiB | 320 | 2.5 GiB |
| 16 MiB | 160 | 2.5 GiB |
| 32 MiB | 80 | 2.5 GiB |
| 64 MiB | 40 | 2.5 GiB |

## 阶段内冷热

每组 250 GiB 按 4 MiB 等价对象计算为 64,000 个对象。脚本先计算对象级
Zipf(alpha=0.99)，再聚合到 20 个等容量 rank，整数权重为：

```text
73 / 6 / 3 / 2 / 1 × 16
```

因此最热 rank 占活动组 5% 容量、承担 73% 阶段操作；所有 20 个 rank 都有
非零访问。每个 rank 的权重再平均拆到五档文件。Zipf 是执行模型，不是 WRF
论文或官方 benchmark 给出的冷热比例。

## 正式阶段

| 阶段 | 时长 | 活动数据 | 最高权重数据 |
|---|---:|---|---|
| `startup_read` | 150 s | 全部 startup rank | `startup/rank_01` |
| `checkpoint_read` | 150 s | 全部 checkpoint rank | `checkpoint/rank_01` |
| `history_read` | 150 s | 全部 history rank | `history/rank_01` |
| `checkpoint_reheat` | 150 s | 全部 checkpoint rank | `checkpoint/rank_01` |

第四阶段与第二阶段引用同一 checkpoint 数据和同一 Zipf 顺序，形成复热。
正式阶段全部为 4 MiB 顺序读、Direct I/O；默认 `THREADS=1`、
`FWD_RATE=max`。

## 使用

```bash
cd /home/chris/ceph-test/SYSU_workload/hpc_wrf_vdbench_v1
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据目录为 `$ANCHOR_ROOT/hpc_wrf_vdbench_v1`。当前配置没有 `hd=`。

## 适用范围

- 用于需要明确阶段内冷热的 HPC 文件生命周期实验。
- 不运行 WRF 数值模式，不复现 NetCDF/HDF5 变量布局。
- 不表达 MPI-IO、collective I/O 或 I/O quilting；需要 MPI 与
  file-per-process 语义时使用 [`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md)。
- 正式测试只读，不模拟 checkpoint/history 写出。
