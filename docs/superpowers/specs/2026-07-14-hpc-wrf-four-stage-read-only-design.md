# HPC WRF 四阶段只读负载设计

## 目标

把 `hpc_wrf_ior_v1` 从当前 8 次、读写混合且时长随吞吐变化的 IOR 调用，简化为 4 个只读阶段。每阶段目标 I/O 时间为 150 秒，正式测试总 I/O 时间约 600 秒；MPI 启停和文件打开、关闭会使墙钟时间略高于 10 分钟。

正式测试只读。`prepare_data.sh` 仍需写入一次，用于提前生成可重复使用的数据集。

## 数据模型

只保留三个等容量语义池，删除正式测试不再使用的旧 checkpoint、旧 history 和独立 initial restart：

| 数据池 | WRF 语义 | 容量 |
|---|---|---:|
| `startup/wrf_state` | 合并表达 `wrfinput` 与 `wrfbdy` 启动状态 | 36 GiB |
| `checkpoint/wrfrst_current` | 可用于恢复的 checkpoint/restart | 36 GiB |
| `history/wrfout_current` | history/output，供分析读取 | 36 GiB |

默认继续使用 `NP=4`、IOR file-per-process。每个语义池由 4 个 9 GiB rank 文件组成，总物理容量约 108 GiB，符合 100–120 GiB 的单负载容量范围。三个池都会在正式测试中被访问，不保留全程不访问的数据。

容量相等是为了使三个数据池和阶段间的冷热容量更易比较，属于单节点缩放参数，不宣称来自 WRF trace。

## 四阶段工作流

| 顺序 | 阶段 | 操作 | 目标 | 冷热意义 |
|---:|---|---|---|---|
| 1 | `startup_read` | 顺序读 | `startup/wrf_state` | 启动状态升温 |
| 2 | `checkpoint_read` | 顺序读 | `checkpoint/wrfrst_current` | checkpoint 首次升温 |
| 3 | `history_read` | 顺序读 | `history/wrfout_current` | history 升温，checkpoint 冷却 |
| 4 | `checkpoint_reheat` | 顺序读 | 同一个 `checkpoint/wrfrst_current` | checkpoint 经过约 150 秒后复热 |

该顺序保留 WRF 输入、restart/checkpoint 和 history/output 的文件语义，但不再模拟 WRF 写出过程，因此应描述为“WRF 文件生命周期启发的 IOR 只读冷热负载”，而不是完整 WRF I/O benchmark。

## IOR 参数

正式阶段统一使用：

```text
-a POSIX
--posix.odirect
-F
-r
-k
-C
-i 1
-D 150
-O minTimeDuration=150
-O stoneWallingWearOut=0
```

- `--posix.odirect` 保证 Direct I/O，减少客户端页缓存影响。
- `minTimeDuration=150` 在设备较快时重复扫描文件，使阶段持续到约 150 秒。
- `-D 150` 在设备较慢时停止继续提交新 I/O，避免一次完整扫描将阶段拖得很长。
- `stoneWallingWearOut=0` 不要求较慢 rank 追平其他 rank 已完成的操作量。
- 不使用外部 `timeout`，避免强制杀死 MPI/IOR。

150 秒限制作用于 IOR 数据传输部分，不包含 MPI 启动、open/close 等开销。正常总墙钟时间应略高于 600 秒；Ceph 或 MPI 系统调用卡死时不构成绝对硬上限。

当 150 秒不足以扫描整个数据池时，阶段可能只读取顺序文件的前部。这是固定阶段时间和完整覆盖不能同时保证时的已接受取舍。

## 文件调整

- `configs/prepare_data.sh.in`：只生成三个 36 GiB 数据池，保留 Direct I/O。
- `configs/run_test.sh.in`：删除写 helper，只保留统一的读 helper和四个阶段。
- `render_config.sh`：默认 `BLOCK_SIZE=9g`、`PHASE_SECONDS=150`，删除 `IOR_ITERATIONS`，渲染 IOR 时间参数。
- `rendered/prepare_data.sh`、`rendered/run_test.sh`：从模板重新生成。
- `tests/validate_hpc_workload.py`：校验 108 GiB、四阶段、正式测试无 `-w`、Direct I/O 和 150 秒双时间约束。
- `README.md`、`SOURCES.md`、`new_workload/WORKLOAD_SUMMARY.md`：同步数据结构、阶段、来源边界和时间说明。

## 验证

1. `validate_model.sh` 通过。
2. 所有 shell 脚本通过 `bash -n`。
3. 渲染后的正式脚本恰好包含四个 IOR 阶段，且不包含写操作。
4. prepare 容量计算为 108 GiB。
5. IOR 参数包含 POSIX Direct I/O、`-D 150`、`minTimeDuration=150` 和 `stoneWallingWearOut=0`。
6. 不执行实际 prepare 或正式测试，避免未经用户单独确认就改写 CephFS 数据。
