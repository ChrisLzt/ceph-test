# HPC WRF checkpoint/restart 冷热负载 IOR v1

## 1. 用途

本负载用于验证存储系统能否识别 HPC 应用中的阶段性文件热度：

- 启动阶段读取输入、边界和 restart 文件；
- 运行阶段写 checkpoint/history 文件；
- 新写出的 checkpoint/history 短时间保持热；
- 恢复阶段再次读取旧 checkpoint，形成复热。

它不运行 WRF 模型，而是使用 IOR 表达 WRF 类天气模拟中的并行文件 I/O 生命周期。

## 2. 权威来源

主要来源：

- NSF NCAR/MMM WRF v3.9.1.1 CONUS-12km benchmark。该 benchmark 用于 WRF 性能评估，计划文档中已确定以它作为 HPC 负载来源。
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
| `input/` | `wrfinput` / `wrfbdy` 类输入和边界文件 | 启动阶段读 |
| `restart/` | 初始 restart 文件 | 启动阶段读 |
| `checkpoint/` | 新旧 checkpoint/restart 代际 | 周期性写、恢复读 |
| `history/` | history/output 文件 | 周期性写、短期读 |

默认数据规模：

| 参数 | 默认值 |
|---|---:|
| MPI ranks | 4 |
| IOR file-per-process | enabled |
| block size per rank | 4 GiB |
| transfer size | 1 MiB |
| 文件基名数量 | 7 |
| 总容量 | 约 112 GiB |

默认使用 file-per-process，是为了更接近 HPC 中每个 rank 参与并行 I/O 的场景，同时降低单节点 CephFS 上 shared-file 锁和元数据争用带来的干扰。后续如要测试 shared-file，可新增配置，不在 v1 混合。

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

- `rendered/prepare_data.sh`：只写入/覆盖基础数据文件；
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
BLOCK_SIZE=4g \
TRANSFER_SIZE=1m \
SEGMENT_COUNT=1 \
PHASE_SECONDS=75 \
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

`prepare_data.sh` 会渲染并执行 `rendered/prepare_data.sh`，创建约 112 GiB 文件集合。这个脚本会覆盖同名 IOR 文件，只应在需要重新造数时运行。

后续正式测试：

```bash
./run_test.sh
```

`run_test.sh` 会渲染并执行 `rendered/run_test.sh`，阶段包括：

1. `startup_read`：读取 input/boundary/restart；
2. `checkpoint_write`：写当前 checkpoint；
3. `checkpoint_hot_read`：读取刚写出的 checkpoint；
4. `history_write`：写当前 history/output；
5. `history_hot_read`：读取刚写出的 history/output；
6. `recovery_reheat_read`：读取旧 checkpoint，观察复热。

默认正式测试包含 8 次 IOR 阶段调用，每阶段通过 IOR `-D 75` 设置 stonewalling 时间上限，并通过 `IOR_ITERATIONS=4` 重复完整 I/O。这样可以产生足够多的 HP 评估样本，避免测试结束时大部分 I/O 仍停留在 evaluation queue 中。实际总时长会包含命令启动和收尾开销，因此会略高于 10 分钟；各阶段实际读写量也会随当时 CephFS 性能变化。

## 7. 当前环境注意事项

本机发现有两套 OpenMPI。`/usr/local/bin/mpirun` 启动当前 IOR 会段错误，`/usr/mpi/gcc/openmpi-4.1.9a1/bin/mpirun` 可以启动 IOR，因此默认使用后者。

## 8. 验收

负载符合度：

- `validate_model.sh` 通过；
- `rendered/prepare_data.sh` 只包含 write/create 类阶段；
- `rendered/run_test.sh` 不执行全量 prepare；
- IOR 输出中各阶段文件路径符合 input/restart/checkpoint/history 生命周期；
- 每阶段无 I/O 错误。

冷热识别：

- `checkpoint/current` 和 `history/current` 在写入及随后读取阶段应升温；
- `checkpoint/old` 在恢复读取阶段应复热；
- `input`、`restart` 在启动读后应逐步冷却；
- 记录 time-to-promote、time-to-demote、time-to-reheat、迁移字节和 P95/P99 时延。

## 9. 已知边界

- 本负载不运行 WRF 物理模式，不评价 WRF 计算性能。
- 本负载不复现 NetCDF 变量布局、真实 timestep 间隔或 WRF 输出频率。
- 默认容量和阶段数量是单节点 CephFS 测试预算下的缩放模型，不是 CONUS-12km 原始数据大小。
- 如果后续获得真实 WRF I/O trace，应优先用 trace 重新拟合阶段和文件大小。
