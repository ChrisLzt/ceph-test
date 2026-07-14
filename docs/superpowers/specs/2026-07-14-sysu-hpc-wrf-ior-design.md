# SYSU HPC WRF IOR 750 GiB 负载设计

## 目标

在 `/home/chris/ceph-test/SYSU_workload` 中新增独立的
`hpc_wrf_ior_v1`，作为现有五个 Vdbench 负载之外的第六个负载。它使用 IOR
保留 MPI 并行顺序 I/O 语义，同时在容量、WRF 文件生命周期、请求大小和阶段时长
上尽量与 `hpc_wrf_vdbench_v1` 对齐。

该负载用于 CephFS 冷热识别，不运行 WRF 数值计算，也不作为官方 WRF 性能结果。
正式阶段保持纯读；造数据阶段单独执行写入。

## 方案选择

考虑过三种方案：

1. **三组等容量的 IOR file-per-process（采用）**：保留 MPI rank 和大文件顺序
   I/O，每组 250 GiB，按 startup、checkpoint、history 和 checkpoint 复热运行。
2. **把 IOR 强制拆成 4/8/16/32/64 MiB 小文件**：可以接近五个 Vdbench 的文件
   分布，但需要大量独立 IOR 调用，削弱 IOR 并行大文件测试的意义，因此不采用。
3. **在单个 IOR 阶段内模拟 Zipf rank 倾斜**：需要让不同 rank 承担不同循环次数
   或拆成多次 MPI 调用，破坏同一次 collective launch 中 rank 对等的语义，留作
   后续 trace 驱动扩展，不纳入 v1。

因此，IOR 版本负责表达 MPI 并行顺序访问和组间生命周期；现有 HPC Vdbench 版本
继续负责表达同一阶段内部的 Zipf(0.99) 精细冷热倾斜。两者互补，不要求配置完全
相同。

## 来源边界

应用语义沿用 WRF/CONUS-12km 场景中的输入、边界、restart/checkpoint 和
history/output 文件生命周期；执行工具使用官方 IOR 的 MPI、POSIX、
file-per-process、block size 和 transfer size 能力。

- WRF 模型：<https://www.mmm.ucar.edu/models/wrf>
- IOR 官方仓库：<https://github.com/hpc/ior>
- IOR 官方文档：<https://ior.readthedocs.io/>

来源只支持文件类型和并行 I/O 方式。三组等容量、750 GiB、四阶段、150 秒和
checkpoint 复热是本冷热识别实验的缩放设计，不宣称为 WRF trace 的实测比例。

## 路径与客户端边界

源码目录：

```text
/home/chris/ceph-test/SYSU_workload/hpc_wrf_ior_v1
```

共享数据路径由运行时的 `ANCHOR_ROOT` 指定：

```text
${ANCHOR_ROOT}/hpc_wrf_ior_v1
```

计划使用：

```text
ANCHOR_ROOT=/ceph-test/SYSU_workload
```

当前不写死 hostfile、客户端主机名、SSH 用户或每节点 rank 数。渲染器提供可选
`MPI_HOSTFILE`；未设置时由本机 `mpirun` 的默认放置策略决定。获得正式客户端清单
后再配置 hostfile，但不改变数据容量和阶段模型。

## 数据结构

三个 WRF 语义组各 250 GiB：

| 数据组 | IOR 文件基名 | 逻辑容量 | 语义 |
|---|---|---:|---|
| `startup` | `startup/wrf_state` | 250 GiB | 输入场和边界状态 |
| `checkpoint` | `checkpoint/wrfrst_current` | 250 GiB | restart/checkpoint |
| `history` | `history/wrfout_current` | 250 GiB | history/output |
| 合计 |  | 750 GiB |  |

默认使用 4 个 MPI rank 和 IOR file-per-process：

```text
NP=4
BLOCK_SIZE=64000m
SEGMENT_COUNT=1
```

因此每个 rank 文件为 62.5 GiB：

```text
64000 MiB = 62.5 GiB
4 × 62.5 GiB = 250 GiB/组
3 × 250 GiB = 750 GiB
```

每组生成 4 个 rank 文件，三个组共 12 个文件。三副本下约占 2250 GiB 原始
空间。IOR 文件大小不套用 Vdbench 的 4～64 MiB 桶；两者只对齐逻辑组容量。

`NP=4` 既是实际 MPI 并发数，也是容量公式的一部分，v1 不允许单独覆盖。客户端
数量可以变化，由 hostfile 把 4 个 rank 放置到可用客户端。

## I/O 参数

统一默认参数：

```text
API=POSIX
NP=4
BLOCK_SIZE=64000m
TRANSFER_SIZE=4m
SEGMENT_COUNT=1
PHASE_SECONDS=150
file-per-process=enabled
Direct I/O=enabled
```

`BLOCK_SIZE` 表示每 rank 文件的数据量；`TRANSFER_SIZE=4m` 才是单次请求大小，
与五个 SYSU Vdbench 负载一致。准备和正式测试都使用 POSIX Direct I/O，降低
客户端页缓存对冷热识别的干扰。

## 工作流

### 配置渲染

`render_config.sh` 将环境变量渲染为：

```text
rendered/prepare_data.sh
rendered/run_test.sh
```

必须显式提供 `ANCHOR_ROOT`。默认 `IOR_BIN` 和 `MPI_RUN` 可以被覆盖；
`MPI_HOSTFILE` 为空时不得生成伪造的客户端配置。

### 造数据

`prepare_data.sh` 只负责准备数据：

1. 将清理范围限制在 `${ANCHOR_ROOT}/hpc_wrf_ior_v1`；
2. 创建 startup、checkpoint 和 history 目录；
3. 分别使用 IOR write、file-per-process 和 Direct I/O 写入 250 GiB；
4. 使用 `-k` 保留文件，并记录每组独立日志。

造数据完成后，三组文件可供多轮正式测试复用。正式运行不得隐式重新造数据。

### 正式测试

正式阶段全部为顺序读：

| 阶段 | 时长 | 读取数据 | 冷热变化 |
|---|---:|---|---|
| `startup_read` | 150 s | startup 250 GiB | startup 升温 |
| `checkpoint_read` | 150 s | checkpoint 250 GiB | checkpoint 升温，startup 冷却 |
| `history_read` | 150 s | history 250 GiB | history 升温，checkpoint 冷却 |
| `checkpoint_reheat` | 150 s | 同一 checkpoint 250 GiB | checkpoint 复热 |

主体 I/O 时间约 600 秒。每个阶段使用 IOR 的 deadline、minimum duration 和
stonewall 控制，使较快设备重复扫描到约 150 秒，并避免较慢设备为完成全量扫描
而无限延长。MPI 启停、open/close 和 CephFS 卡顿仍可能让墙钟时间略高于 10 分钟；
该机制不是系统级硬超时。

## 冷热含义

该 IOR 负载只提供**组间冷热**：一个阶段内被选中的 250 GiB 数据组都属于当前
活跃集合，组内 4 个 rank 文件被等价访问。它不提供组内 Zipf 热点，也不应把
某个 rank 解释为更热。

预期可观察到：

- startup 在第一阶段升温，之后逐步冷却；
- checkpoint 在第二阶段升温、第三阶段冷却、第四阶段复热；
- history 在第三阶段升温；
- 三组数据都至少被访问一次，不存在全程不访问的数据。

如果实验目标是判断 250 GiB 组内部哪些文件更热，应改用
`hpc_wrf_vdbench_v1`，而不是向 IOR v1 叠加人为 Zipf。

## 代码结构

计划新增：

```text
SYSU_workload/hpc_wrf_ior_v1/
├── README.md
├── SOURCES.md
├── configs/
│   ├── prepare_data.sh.in
│   └── run_test.sh.in
├── rendered/                 # 运行时生成，不提交
├── tests/
│   └── validate_hpc_ior.py
├── render_config.sh
├── prepare_data.sh
├── run_test.sh
└── validate_model.sh
```

同时更新 `SYSU_workload/README.md` 和 `validate_all.sh`，使总览明确为“五个
Vdbench + 一个 IOR”，并将 IOR 模型校验纳入总体验证。

## 校验与验收

1. 渲染器拒绝缺失或非绝对路径的 `ANCHOR_ROOT`。
2. 准备脚本恰好创建三个 250 GiB 数据组，总容量 750 GiB。
3. 默认恰好使用 4 rank、62.5 GiB/rank、4 MiB transfer。
4. 正式脚本恰好四个只读阶段，不包含 IOR write。
5. checkpoint 的第二、第四阶段必须指向同一文件基名。
6. 所有正式阶段启用 file-per-process、POSIX Direct I/O 和 150 秒时间控制。
7. 脚本不硬编码客户端或 hostfile；可选 hostfile 只能由运行时提供。
8. `SYSU_workload/validate_all.sh` 同时通过五个 Vdbench 和一个 IOR 的校验。
9. 不在实现或验证阶段向 CephFS 造数据，不执行正式性能测试。

## 适用范围

- 适合比较冷热模块开启/关闭时，MPI并行顺序读和文件生命周期下的行为。
- 不模拟 WRF 数值计算、NetCDF/HDF5布局、真实输出频率或容量比例。
- 不评价组内细粒度冷热识别准确率。
- 不把 4 个 IOR rank 与 12 个存储节点一一对应；MPI客户端布局是独立运行参数。
- 运行前必须确认三副本集群有至少 2250 GiB（约 2.20 TiB）原始可用空间，并为 Ceph 恢复、
  backfill和元数据保留余量。
