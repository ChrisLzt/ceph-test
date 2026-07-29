# WRF-derived Vdbench Zipf 冷热负载设计

## 目标

在保留 `SINGLE_workload/hpc_wrf_ior_v1` 的前提下，新增
`SINGLE_workload/hpc_wrf_vdbench_v1`。新负载使用 WRF 的输入、restart 和
history 文件生命周期组织四个纯读阶段，并在每个活动数据组内部使用
Zipf(0.99) 访问权重制造明确的冷热区分。

本负载用于 CephFS 冷热识别，不用于评价 WRF 计算性能、MPI 并行效率或
标准 HPC benchmark 成绩。

## 来源边界

WRF 来源负责支撑以下语义：

- startup 阶段读取输入和边界状态；
- restart/checkpoint 文件可在恢复时读取；
- history/output 文件可在分析阶段读取；
- 同一个 checkpoint 冷却后再次读取形成复热。

Zipf(0.99)、容量缩放、四阶段和阶段时长属于受控冷热识别实验参数，不是
WRF 官方 trace 给出的比例。文档不得将 Zipf 权重描述成 WRF 实测分布。

## 目录与兼容性

新增目录：

```text
SINGLE_workload/hpc_wrf_vdbench_v1/
```

现有目录保持不变：

```text
SINGLE_workload/hpc_wrf_ior_v1/
```

Vdbench 版本使用独立 CephFS anchor：

```text
/mnt/cephfs/hpc_wrf_vdbench_v1
```

因此两个版本可以分别造数和运行，不共享或覆盖数据。

## 数据构造

高层数据组保持为三类：

```text
startup
checkpoint
history
```

每组拆为 20 个等容量 rank：

```text
rank_01 ... rank_20
```

每个 rank 包含 120 个 16 MiB 文件，容量为 1.875 GiB。每个高层数据组
包含 2400 个文件、容量为 37.5 GiB；三个数据组合计 7200 个文件、
112.5 GiB。

使用 4 MiB Ceph 对象作为建模粒度时，每个 16 MiB 文件对应 4 个对象，
每个 rank 对应 480 个对象，每组对应 9600 个对象。

## Zipf 权重推导

对每组 9600 个对象按下式计算访问概率：

\[
P(i)=\frac{i^{-0.99}}{\sum_{j=1}^{9600}j^{-0.99}}
\]

每 480 个连续对象聚合到一个等容量 rank。原始浮点占比四舍五入为整数，
保证每个 rank 至少获得 1%，并调整总和为 100%，得到：

```text
68 / 7 / 4 / 3 / 2 / 2 / 1 x 14
```

由此得到以下可验证关系：

- 每个 rank 占活动数据组容量的 5%；
- rank_01 的 5% 容量承担 68% 阶段访问；
- rank_01~02 的 10% 容量承担 75% 阶段访问；
- rank_01~03 的 15% 容量承担 79% 阶段访问；
- rank_01~06 的 30% 容量承担 86% 阶段访问；
- 所有 rank 的访问权重均非零。

## 正式测试阶段

正式测试只读，共四个阶段，每阶段 150 秒，总 I/O 时间 600 秒：

| 阶段 | 活动数据组 | 最高权重数据 | 目的 |
|---|---|---|---|
| `startup_read` | startup 的 20 个 rank | `startup/rank_01` | 输入和边界状态升温 |
| `checkpoint_read` | checkpoint 的 20 个 rank | `checkpoint/rank_01` | checkpoint 首次升温 |
| `history_read` | history 的 20 个 rank | `history/rank_01` | history 升温并使 checkpoint 冷却 |
| `checkpoint_reheat` | checkpoint 的 20 个 rank | `checkpoint/rank_01` | 同一 checkpoint 热点复热 |

第四阶段复用第二阶段完全相同的 checkpoint rank 和 Zipf 顺序，不旋转
checkpoint 内部热点。

单阶段中，活动数据组占总容量的三分之一。活动组内所有 rank 都被访问，
但访问密度由 Zipf 权重区分；另外两个高层数据组在该阶段不活动。三个
高层数据组在完整测试中均至少访问一次。

## Vdbench I/O 参数

正式测试采用：

```text
operation=read
fileio=sequential
fileselect=random
xfersize=1m
threads=4
openflags=o_direct
fwdrate=max
elapsed=150
interval=1
abort_failed_skew=2
```

`fileselect=random` 只负责从 rank 文件池选择文件；文件内部保持顺序读取。
`skew` 用于控制 20 个 rank 的访问比例，Vdbench 的实际偏差检查阈值为 2%。

造数据配置与正式测试配置分离：

- `prepare_data.vdb` 只负责清理并创建数据；
- `run_test.vdb` 不包含 `format=`，不会重新造数；
- 两类配置都使用单节点和 Direct I/O。

## 文件结构

新增负载至少包含：

```text
README.md
SOURCES.md
configs/prepare_data.vdb.in
configs/run_test.vdb.in
rendered/prepare_data.vdb
rendered/run_test.vdb
prepare_data.sh
run_test.sh
render_config.sh
validate_model.sh
tests/validate_hpc_vdbench_workload.py
```

`render_config.sh` 负责环境变量替换，并拒绝未解析模板变量。wrapper 脚本
分别只调用 prepare 或 run 配置。

## 验证要求

静态验证必须检查：

1. 三个高层数据组、每组 20 个 rank；
2. 每个 rank 为 120 个 16 MiB 文件；
3. 总容量为 112.5 GiB，处于单负载 100~120 GiB 预算内；
4. 每阶段 20 个 skew 的总和为 100；
5. 权重严格为 `68/7/4/3/2/2/1x14`；
6. 四个阶段均为纯读、顺序文件 I/O、1 MiB 请求；
7. 四个阶段均为 150 秒且使用 `fwdrate=max`；
8. checkpoint 首次读取和复热引用相同 FSD 和相同权重；
9. prepare 配置包含 clean/create，run 配置不包含 format；
10. 所有配置均为单节点、Direct I/O，且不残留旧路径；
11. `hpc_wrf_ior_v1` 目录仍然存在且不被新负载覆盖。

只执行渲染、脚本语法和模型静态验证。除非用户另行要求，不在设计实现
过程中对 `/mnt/cephfs` 执行造数或正式测试。

## 已知限制

- 不运行真实 WRF 数值模式；
- 不复现 NetCDF/HDF5 变量布局；
- 不表达 MPI rank、MPI-IO collective 或 I/O quilting；
- 不模拟 checkpoint/history 写出；
- Zipf(0.99) 是冷热识别执行模型，不是 WRF trace；
- `fwdrate=max` 下仍须以 Vdbench 输出确认实际 skew 未超过允许偏差。
