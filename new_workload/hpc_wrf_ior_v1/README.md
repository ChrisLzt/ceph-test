# HPC WRF 文件生命周期只读冷热负载 IOR v1

## 1. 用途

本负载用于验证存储系统能否识别 HPC 应用中的阶段性文件热度：

- 启动阶段读取合并后的输入和边界状态；
- checkpoint 阶段首次读取 restart 文件；
- history 阶段读取输出文件，使 checkpoint 冷却；
- 恢复阶段再次读取同一个 checkpoint，形成复热。

它不运行 WRF 模型，而是使用 IOR 表达 WRF 类天气模拟中的只读文件生命周期。正式测试只读；造数据阶段仍需提前写入文件。

## 2. 权威来源

主要来源：

- NSF NCAR/MMM WRF v3.9.1.1 CONUS-12km benchmark。该 benchmark 用于 WRF 性能评估，本套件采用它作为 HPC 应用语义来源。
- WRF 模型使用 `wrfinput`、`wrfbdy`、`wrfrst`、`wrfout` 等输入、边界、restart 和 history/output 文件；本负载保留这些文件生命周期语义。
- NCAR/MMM WRF 模型页面：<https://www.mmm.ucar.edu/models/wrf>
- CONUS-12km WRF 使用案例示例：<https://arxiv.org/abs/2409.07232>

工具来源：

- IOR/mdtest 官方仓库：<https://github.com/hpc/ior>
- IOR 官方文档入口：<https://ior.readthedocs.io/>

详细映射见 [SOURCES.md](SOURCES.md)。

## 3. 负载逻辑

IOR 文件名按 WRF 语义分组：

| 目录 | 文件语义 | 访问阶段 |
|---|---|---|
| `startup/` | 合并表达 `wrfinput` / `wrfbdy` 输入和边界状态 | 启动阶段读 |
| `checkpoint/` | checkpoint/restart | 首次读、冷却后复热 |
| `history/` | history/output | 分析读取 |

默认数据规模：

| 参数 | 默认值 |
|---|---:|
| MPI ranks | 4 |
| IOR file-per-process | enabled |
| block size per rank | 9,600 MiB（9.375 GiB） |
| transfer size | 4 MiB |
| 文件基名数量 | 3 |
| 单池容量 | 37.5 GiB |
| 总容量 | 112.5 GiB |

默认使用 file-per-process，是为了保留每个 rank 参与并行 I/O 的语义，同时降低单节点 CephFS 上 shared-file 锁和元数据争用带来的干扰。三个数据池等容量是便于比较冷热容量的单节点缩放参数，不是 WRF trace 给出的容量比例。

IOR 的 `BLOCK_SIZE=9600m` 表示每个 MPI rank 在一个数据池中的数据量，不是单次 I/O 请求大小；`4 rank × 9,600 MiB = 37.5 GiB`。可与 Vdbench `xfersize` 对比的是 `TRANSFER_SIZE=4m`，所以当前 IOR 与五个正式 Vdbench 负载采用相同的 4 MiB 请求粒度。两类工具仍有 MPI file-per-process 与 Vdbench 文件集模型的语义差异，不能把工具差异误判为冷热模块开销。

## 4. 文件结构

- [configs/prepare_data.sh.in](configs/prepare_data.sh.in)：只造数据的 IOR 脚本模板。
- [configs/run_test.sh.in](configs/run_test.sh.in)：只跑测试阶段的 IOR 脚本模板。
- `rendered/prepare_data.sh`：渲染后的造数据脚本。
- `rendered/run_test.sh`：渲染后的正式测试脚本。
- [prepare_data.sh](prepare_data.sh)：只执行造数据。
- [run_test.sh](run_test.sh)：只执行正式测试，不重新创建全量数据集。
- [validate_model.sh](validate_model.sh)：渲染并校验模型、容量和脚本结构。

本目录不提供外部冷热真值表。冷热判断由使用者结合阶段、文件路径和被测系统观测自行判断。

## 5. 生成配置

```bash
cd /home/chris/ceph-test/new_workload/hpc_wrf_ior_v1
./render_config.sh
```

默认生成两个独立脚本：

- `rendered/prepare_data.sh`：清理旧版数据并写入三个基础数据池；
- `rendered/run_test.sh`：执行正式测试阶段。

也可以只渲染其中一个：

```bash
./render_config.sh prepare
./render_config.sh run
```

常用环境变量：

```bash
ANCHOR=/mnt/cephfs/hpc_wrf_ior_v1 \
IOR_BIN=/home/chris/PDSL/ior/src/ior \
MPI_RUN=/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun \
NP=4 \
BLOCK_SIZE=9600m \
TRANSFER_SIZE=4m \
SEGMENT_COUNT=1 \
PHASE_SECONDS=150 \
./render_config.sh
```

默认数据路径为 `/mnt/cephfs/hpc_wrf_ior_v1`，不再添加 `new_workload/` 中间层。

## 6. 执行

运行前先检查模型：

```bash
./validate_model.sh
```

第一次造数据：

```bash
./prepare_data.sh
```

`prepare_data.sh` 会渲染并执行 `rendered/prepare_data.sh`，先删除旧版的 `input/`、`restart/`、`wrfrst_old*` 和 `wrfout_old*` 数据，再创建三个各 37.5 GiB、合计 112.5 GiB 的文件池。这个脚本具有破坏性，只应在需要重新造数且确认旧版 HPC 数据无需保留时运行。

后续正式测试：

```bash
./run_test.sh
```

`run_test.sh` 会渲染并执行 `rendered/run_test.sh`，阶段包括：

1. `startup_read`：读取 `startup/wrf_state`；
2. `checkpoint_read`：首次读取 `checkpoint/wrfrst_current`；
3. `history_read`：读取 `history/wrfout_current`，使 checkpoint 冷却；
4. `checkpoint_reheat`：再次读取同一个 checkpoint，观察复热。

正式测试只有读操作。每阶段使用 POSIX Direct I/O，并同时设置 `minTimeDuration=150` 和 `-D 150`：设备较快时循环读取到约 150 秒，设备较慢时在约 150 秒停止提交新 I/O。`stoneWallingWearOut=0` 避免为追平 rank 操作量继续延长阶段。四阶段 I/O 时间约 600 秒，加上 MPI 启停和文件打开/关闭后，总墙钟时间通常略高于 10 分钟。

150 秒限制针对数据传输，不是系统级硬超时；Ceph 或 MPI 调用卡死时仍可能延长。若 150 秒不足以完整扫描 37.5 GiB 数据池，顺序读可能只覆盖文件前部，这是固定阶段时间的已知取舍。

## 7. 当前环境注意事项

本机发现有两套 OpenMPI。`/usr/local/bin/mpirun` 启动当前 IOR 会段错误，`/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun` 可以启动 IOR，因此默认使用后者。

## 8. 验收

负载符合度：

- `validate_model.sh` 通过；
- `rendered/prepare_data.sh` 只包含旧版数据清理和 write/create 类阶段；
- `rendered/run_test.sh` 不执行全量 prepare；
- IOR 输出中各阶段文件路径符合 startup/checkpoint/history 生命周期；
- 每阶段无 I/O 错误。

冷热识别：

- `startup/wrf_state` 在第一阶段升温后逐步冷却；
- `checkpoint/wrfrst_current` 在第二阶段升温、第三阶段冷却、第四阶段复热；
- `history/wrfout_current` 在第三阶段升温；
- 记录 time-to-promote、time-to-demote、time-to-reheat、迁移字节和 P95/P99 时延。

## 9. 已知边界

- 本负载不运行 WRF 物理模式，不评价 WRF 计算性能。
- 正式测试不模拟 checkpoint/history 写出，只评价只读冷热识别。
- 本负载不复现 NetCDF 变量布局、真实 timestep 间隔或 WRF 输出频率。
- 默认等容量数据池、四阶段和 150 秒时长是单节点 CephFS 缩放模型，不是 CONUS-12km trace 参数。
- 如果后续获得真实 WRF I/O trace，应优先用 trace 重新拟合阶段和文件大小。
