# SYSU GraphChi Vdbench 冷热负载

这是 12 节点、三副本环境使用的 750 GiB 版本。它把 GraphChi Parallel
Sliding Windows（PSW）的 shard 访问关系映射成 Vdbench 阶段，不运行
GraphChi 图算法。

## 来源与边界

应用来源是 Kyrola、Blelloch、Guestrin 的 *GraphChi: Large-Scale Graph
Computation on Just a PC*（OSDI 2012，CCF-A）。算法和 generated graph
推导过程见
[`../../new_workload/graph_graphchi_vdbench_v1/SOURCES.md`](../../new_workload/graph_graphchi_vdbench_v1/SOURCES.md)。

PSW 支持“当前 memory-shard 完整读取、其他 shard 读取 sliding window”的
访问逻辑。`75/13/6/6` 是单节点版确定性 generated graph 的推导结果，SYSU
版本复用该结果并扩大文件容量；它不是论文规定的固定比例，也不是生产图 trace。

## 数据构造

4 个 shard 等容量：

| 数据池 | 容量 | 文件数 | 作用 |
|---|---:|---:|---|
| `shard_00` | 187.5 GiB | 18,600 | interval 0 |
| `shard_01` | 187.5 GiB | 18,600 | interval 1 |
| `shard_02` | 187.5 GiB | 18,600 | interval 2 |
| `shard_03` | 187.5 GiB | 18,600 | interval 3 |
| 合计 | 750 GiB | 74,400 | — |

每个 shard 使用 600 个 320 MiB 单元，内部文件分布为：

| 文件大小 | 文件数 | 容量 |
|---:|---:|---:|
| 4 MiB | 9,600 | 37.5 GiB |
| 8 MiB | 4,800 | 37.5 GiB |
| 16 MiB | 2,400 | 37.5 GiB |
| 32 MiB | 1,200 | 37.5 GiB |
| 64 MiB | 600 | 37.5 GiB |

不在 shard 内部叠加 Zipf；每个 shard 的阶段权重平均拆到五档文件。

## 正式阶段

5 个阶段各 120 秒，总 I/O 时间 600 秒：

| 阶段 | `shard_00` | `shard_01` | `shard_02` | `shard_03` |
|---|---:|---:|---:|---:|
| `iter1_i0` | 75% | 13% | 6% | 6% |
| `iter1_i1` | 6% | 75% | 13% | 6% |
| `iter1_i2` | 6% | 6% | 75% | 13% |
| `iter1_i3` | 13% | 6% | 6% | 75% |
| `iter2_i0` | 75% | 13% | 6% | 6% |

前四阶段覆盖一轮完整 interval，最后阶段重新处理 interval 0，使
`shard_00` 复热。只截取第二轮第一个 interval 是 10 分钟预算下的实验设计，
不是 GraphChi 固定要求。

正式阶段全部为 4 MiB 顺序读、Direct I/O；默认 `THREADS=1`、
`FWD_RATE=max`。四个 shard 在每个阶段都有非零访问。

## 使用

```bash
cd /home/chris/ceph-test/SYSU_workload/graph_graphchi_vdbench_v1
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据目录为 `$ANCHOR_ROOT/graph_graphchi_vdbench_v1`。当前配置没有 `hd=`。

## 适用范围

- 用于评价 shard 级热点迁移和复热。
- 不执行 PageRank、顶点更新、message passing 或收敛判断。
- 不模拟 GraphChi 原生 shard 文件格式。
- 增加文件容量不会重新计算图连接；如需更换图结构，应先在单节点推导流程中
  重新生成比例，再更新 SYSU 配置。
