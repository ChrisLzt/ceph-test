# SYSU WRF 文件生命周期 IOR 负载

这是 12 节点、三副本测试套件中的 MPI 并行 HPC 备选实现。它不运行 WRF
计算，而是使用 IOR 表达 startup、checkpoint、history 和 checkpoint 复热。

## 来源与边界

WRF 官方资料提供输入/边界、restart/checkpoint 和 history/output 文件语义；
IOR 官方工具提供 MPI、POSIX、file-per-process 与 Direct I/O。详细映射见
[SOURCES.md](SOURCES.md)。

三组等容量、750 GiB、`NP=4`、阶段时长和 checkpoint 复热是冷热识别实验
设计，不是 WRF trace 参数。本实现保留 MPI/file-per-process 语义，但不提供
Vdbench 版本的组内 Zipf。

## 数据构造

| 数据组 | 文件基名 | 容量 | rank 文件数 |
|---|---|---:|---:|
| `startup` | `wrf_state` | 250 GiB | 4 |
| `checkpoint` | `wrfrst_current` | 250 GiB | 4 |
| `history` | `wrfout_current` | 250 GiB | 4 |
| 合计 | — | 750 GiB | 12 |

固定参数：

| 参数 | 值 | 含义 |
|---|---:|---|
| `NP` | 4 | 4 个 MPI rank |
| `-F` | 启用 | 每个 rank 使用独立文件 |
| `BLOCK_SIZE` | 64000 MiB | 每 rank、每数据组 62.5 GiB |
| `TRANSFER_SIZE` | 4 MiB | 单次 I/O 请求 |
| `SEGMENT_COUNT` | 1 | 每 rank 一个 block |

因此每个数据组有 4 个 62.5 GiB 文件。IOR 文件名带 rank 后缀；prepare 与
run 必须使用相同路径、文件基名和 `NP=4`。

## 正式阶段

| 阶段 | 时长 | 读取数据 | 热容量口径 |
|---|---:|---|---:|
| `startup_read` | 150 s | startup 的 4 个 rank 文件 | 250 GiB |
| `checkpoint_read` | 150 s | checkpoint 的 4 个 rank 文件 | 250 GiB |
| `history_read` | 150 s | history 的 4 个 rank 文件 | 250 GiB |
| `checkpoint_reheat` | 150 s | 同一 checkpoint 文件 | 250 GiB |

每阶段只活动一个数据组，即总容量的三分之一承担该阶段全部请求。组内 4 个 rank
以相同 IOR 参数运行，没有预设的热点 rank；实际完成量仍可能受客户端和文件
性能差异影响。

正式测试为 POSIX 顺序读、4 MiB Direct I/O。每阶段同时设置 `-D 150`、
`minTimeDuration=150` 和 `stoneWallingWearOut=0`，主体 I/O 时间约 600 秒；
加上四次 MPI 启停、打开和关闭文件，总墙钟时间通常略高于 10 分钟。该时长
不是系统级强制超时，Ceph 或 MPI 阻塞时仍可能延长。

## 使用

先验证：

```bash
cd /home/chris/ceph-test/SYSU_workload/hpc_wrf_ior_v1
./validate_model.sh
```

第一次造数据：

```bash
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
```

该命令会删除并重建
`/ceph-test/SYSU_workload/hpc_wrf_ior_v1`。后续只运行：

```bash
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

需要多客户端时显式提供 hostfile：

```bash
ANCHOR_ROOT=/ceph-test/SYSU_workload \
MPI_HOSTFILE=/path/to/hosts \
MPI_RUN=mpirun \
IOR_BIN=/home/chris/PDSL/ior/src/ior \
./run_test.sh
```

hostfile 必须为 4 个 MPI rank 提供可用 slot。建议 prepare 与 run 保持相同
hostfile，以减少客户端差异；文件匹配的硬要求是共享路径、文件基名和 `NP`
一致。

## 适用范围

- 用于保留 MPI rank 与 file-per-process 语义的组间冷热实验。
- 不适合评价单阶段内的明确冷热层次；该需求使用 Vdbench 版本。
- 不运行 WRF 数值模式，不复现 NetCDF 布局或 collective I/O。
- 正式阶段只读，不模拟 checkpoint/history 写出。
