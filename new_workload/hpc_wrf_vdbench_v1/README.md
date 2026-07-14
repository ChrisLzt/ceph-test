# WRF 文件生命周期 Zipf 冷热负载 Vdbench v1

## 1. 用途

本负载使用 Vdbench 在 CephFS 上表达 WRF 类应用的三个文件语义组：

- startup：输入和边界状态；
- checkpoint：restart/checkpoint；
- history：history/output。

正式测试只读，通过四个阶段完成 startup 升温、checkpoint 首次升温、
history 热点迁移和同一 checkpoint 复热。每个活动数据组内部使用
Zipf(0.99) 权重，因此单个阶段内同时存在高频和低频数据。

它不运行 WRF，也不评价 WRF、MPI 或存储性能成绩。现有
[`hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md) 保留，用于后续需要 MPI
rank、file-per-process 和 IOR 语义的测试。

## 2. 来源与参数边界

WRF 官方文档支撑输入/边界、restart 和 history/output 的文件类型及
生命周期。Vdbench 只负责把这些阶段转换为 CephFS 读请求。

必须区分：

- WRF 决定三个数据组和 checkpoint 复热顺序；
- Zipf(0.99)、112.5 GiB、20 个 rank 和每阶段 150 秒是受控实验参数；
- Zipf 权重不是 WRF trace 实测比例。

详细来源见 [SOURCES.md](SOURCES.md)。

## 3. 数据构造

三个高层数据组分别拆成 20 个等容量 rank：

```text
startup/rank_01 ... rank_20
checkpoint/rank_01 ... rank_20
history/rank_01 ... rank_20
```

| 项目 | 每个 rank | 每个数据组 | 总计 |
|---|---:|---:|---:|
| rank 数 | 1 | 20 | 60 |
| 文件数 | 120 | 2400 | 7200 |
| 单文件大小 | 16 MiB | 16 MiB | 16 MiB |
| 容量 | 1.875 GiB | 37.5 GiB | 112.5 GiB |

按 4 MiB Ceph 对象建模，每个文件对应 4 个对象，每个 rank 对应 480 个
对象，每个数据组对应 9600 个对象。

## 4. Zipf 分布

先在每组 9600 个对象上计算：

\[
P(i)=\frac{i^{-0.99}}{\sum_{j=1}^{9600}j^{-0.99}}
\]

然后每 480 个连续对象聚合成一个等容量 rank。整数化后保证所有 rank
至少获得 1% 访问，最终权重为：

```text
68 / 7 / 4 / 3 / 2 / 2 / 1 × 14
```

因此在一个活动数据组内部：

| 容量范围 | 阶段访问占比 |
|---:|---:|
| rank_01：5%容量 | 68% |
| rank_01~02：10%容量 | 75% |
| rank_01~03：15%容量 | 79% |
| rank_01~06：30%容量 | 86% |
| 全部rank：100%容量 | 100% |

所有 20 个 rank 都有非零访问，阶段内不存在“被纳入活动组但完全不读”的
数据。

## 5. 正式测试阶段

默认四阶段各 150 秒，总 I/O 时间 600 秒：

| 阶段 | 读写 | 活动数据 | 最高权重数据 | 目的 |
|---|---|---|---|---|
| `startup_read` | 读 | 全部 startup rank | `startup/rank_01` | 输入和边界状态升温 |
| `checkpoint_read` | 读 | 全部 checkpoint rank | `checkpoint/rank_01` | checkpoint 首次升温 |
| `history_read` | 读 | 全部 history rank | `history/rank_01` | history 升温、checkpoint 冷却 |
| `checkpoint_reheat` | 读 | 全部 checkpoint rank | `checkpoint/rank_01` | 同一 checkpoint 热点复热 |

第四阶段复用第二阶段完全相同的 checkpoint rank 和 Zipf 顺序，不旋转
内部热点。

每阶段活动数据组容量为 37.5 GiB，占总容量三分之一。活动组内部由
Zipf 权重区分冷热；另外两个高层数据组在该阶段不活动，但三个高层组在
完整测试中都至少被访问一次。

## 6. I/O 参数

正式测试默认使用：

```text
operation=read
fileio=sequential
fileselect=random
xfersize=4m
threads=4
openflags=o_direct
fwdrate=1000
elapsed=150
abort_failed_skew=2
```

`fileselect=random` 选择 rank 内的文件，单个文件内部仍按顺序读取。
固定 `fwdrate=1000` 使 Vdbench 能稳定执行各 rank 的目标比例；
`abort_failed_skew=2` 用于阻止实际访问比例相对目标偏差过大。

## 7. 工作流

渲染并验证：

```bash
cd /home/chris/ceph-test/new_workload/hpc_wrf_vdbench_v1
./validate_model.sh
```

第一次创建数据：

```bash
./prepare_data.sh
```

后续只运行正式测试：

```bash
./run_test.sh
```

默认路径为 `/mnt/cephfs/hpc_wrf_vdbench_v1`。`prepare_data.sh` 会清理并
重建该负载的数据；重复测试不应再次执行 prepare。

## 8. 验收与限制

静态模型应满足：

- 60 个 FSD rank、7200 个文件、112.5 GiB；
- 四阶段均为纯读、4 MiB、Direct I/O；
- 每阶段 Zipf 权重总和为 100，且没有 0 权重；
- checkpoint 首次读取和复热引用同一批 FSD；
- run 配置不包含 `format=`；
- `hpc_wrf_ior_v1` 仍然存在。

已知限制：

- 不运行真实 WRF 数值模式；
- 不复现 NetCDF/HDF5 变量布局；
- 不表达 MPI-IO、collective I/O 或 I/O quilting；
- 不模拟 checkpoint/history 写入；
- Zipf(0.99) 是执行模型，不是 WRF trace。
