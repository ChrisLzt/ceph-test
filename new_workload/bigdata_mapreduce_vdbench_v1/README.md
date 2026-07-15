# MapReduce 文件冷热负载

## 来源与设计逻辑

主要来源是 Abad 等对 Yahoo! Hadoop/MapReduce 生产 trace 的分析：
*A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal
Locality and Arrival Patterns*（IEEE IISWC 2012，未被当前 CCF 推荐目录收录）。
论文支持文件访问高度偏斜、明显 temporal locality 和大量 inactive storage；
详细原始比例与边界见
[SOURCES.md](SOURCES.md)。

本模型去掉全程不访问池，将其容量按论文原始活跃池比例重新分配，得到取整后的
`4/4/4/88%`。三个小池轮流成为热点，背景池始终保持访问。池内文件级
Zipf(0.99) 是引用 YCSB 参数的受控实验设计，不是 Yahoo trace 的逐文件重放。

## 数据构造

| 数据池 | 单元 | 容量 | rank | 每 rank 单元 |
|---|---:|---:|---:|---:|
| `pool_01` | 96 | 4.5 GiB | 24 | 4 |
| `pool_02` | 96 | 4.5 GiB | 24 | 4 |
| `pool_03` | 96 | 4.5 GiB | 24 | 4 |
| `background` | 2,112 | 99 GiB | 24 | 88 |

每个单元含 4 个 4 MiB、2 个 8 MiB 和 1 个 16 MiB 文件。每个固定大小档
独立计算 Zipf(0.99)，再聚合到该池 24 个等容量 rank；因此既保留 pool 级论文
比例，也在 pool 内形成文件级长尾热度。

## 正式阶段

| 时间 | 热点状态 |
|---:|---|
| 0–150 s | pool_01：`85/1/1/13%` |
| 150–300 s | pool_02：`1/85/1/13%` |
| 300–450 s | pool_03：`1/1/85/13%` |
| 450–600 s | pool_01 复热：`85/1/1/13%` |

热点在阶段边界直接切换，background 始终承担 13% 访问。全部为 4 MiB 顺序读、
Direct I/O、`fwdrate=max`；600 秒总时长不变。

## 适用范围

适合观察小热点池迁移和复热；不运行 Hadoop，不模拟 HDFS block placement、
NameNode RPC 或作业计算。论文的 open/access 指标不能直接等同于 read bytes。

数据默认位于 `/mnt/cephfs/bigdata_mapreduce_vdbench_v1`。prepare 每批最多创建
20 个 rank，完成一次后可反复执行 `run_test.sh`。
