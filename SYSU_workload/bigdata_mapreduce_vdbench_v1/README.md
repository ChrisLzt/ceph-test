# SYSU MapReduce Vdbench 冷热负载

这是 12 节点、三副本环境使用的 750 GiB 版本。它继承单节点 MapReduce
负载的文件池与 temporal-locality 模型，只扩大容量并引入统一的混合文件大小。

## 来源与边界

主要来源是 Yahoo Hadoop/MapReduce 生产 trace 分析论文
*A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal
Locality and Arrival Patterns*（IEEE IISWC 2012）。详细参数映射见
[`../../new_workload/bigdata_mapreduce_vdbench_v1/SOURCES.md`](../../new_workload/bigdata_mapreduce_vdbench_v1/SOURCES.md)。

论文支持年轻文件容量较小、访问高度集中以及大量 inactive storage。当前模型
按既定方案去掉全程不访问池，并把 inactive 容量重新分配给四个可访问池。
`30/30/30/660 GiB`、阶段时长和混合文件大小是扩容后的实验参数，不是论文
原始文件分布。

## 数据构造

| 数据池 | 容量 | 文件数 | 作用 |
|---|---:|---:|---|
| `pool_01` | 30 GiB | 2,976 | 候选热点 A |
| `pool_02` | 30 GiB | 2,976 | 候选热点 B |
| `pool_03` | 30 GiB | 2,976 | 候选热点 C |
| `pool_04` | 660 GiB | 65,472 | 活跃背景数据 |
| 合计 | 750 GiB | 74,400 | — |

前三池各使用 96 个 320 MiB 单元，背景池使用 2,112 个单元。每个池内部的
4/8/16/32/64 MiB 五档文件容量相同。例如每个 30 GiB 池包含：

| 文件大小 | 文件数 | 容量 |
|---:|---:|---:|
| 4 MiB | 1,536 | 6 GiB |
| 8 MiB | 768 | 6 GiB |
| 16 MiB | 384 | 6 GiB |
| 32 MiB | 192 | 6 GiB |
| 64 MiB | 96 | 6 GiB |

因此文件大小只改变文件数量，不改变池容量或热点比例。

## 正式阶段

4 个阶段各 150 秒，总 I/O 时间 600 秒：

| 阶段 | `pool_01` | `pool_02` | `pool_03` | `pool_04` | 热点 |
|---|---:|---:|---:|---:|---|
| `hot_a` | 85% | 1% | 1% | 13% | A |
| `hot_b` | 1% | 85% | 1% | 13% | B |
| `hot_c` | 1% | 1% | 85% | 13% | C |
| `reheat_a` | 85% | 1% | 1% | 13% | A 复热 |

85% 接近论文 PROD 中 1 天内文件贡献 85.41% accesses 的观测；非热点池的
`1/1/13` 是把剩余 15% 分给其他可访问数据的工程映射。每个池的权重平均拆到
五档文件，例如 85% 热点池的每档文件承担 17% 阶段操作。

正式阶段全部为 4 MiB 顺序读、Direct I/O；默认 `THREADS=1`、
`FWD_RATE=max`。所有四个池在每个阶段都有非零访问。

## 使用

```bash
cd /home/chris/ceph-test/SYSU_workload/bigdata_mapreduce_vdbench_v1
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据目录为 `$ANCHOR_ROOT/bigdata_mapreduce_vdbench_v1`。`prepare_data.sh`
会清理并重建 750 GiB 数据；后续测试只执行 `run_test.sh`。当前配置没有
`hd=`，I/O 由运行脚本的客户端发起。

## 适用范围

- 用于评价小容量热点迁移、冷却和复热。
- 不运行 Hadoop，也不模拟 HDFS block placement、NameNode RPC 或作业计算。
- trace 的 open 次数不等于 read bytes；4 MiB 请求和文件大小是实验参数。
- 结果不能表述为 Yahoo 集群的完整 I/O 重放。
