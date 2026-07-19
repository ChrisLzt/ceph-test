# MapReduce 文件冷热负载

## 来源与设计逻辑

主要来源是 Abad 等对 Yahoo! Hadoop/MapReduce 生产 trace 的分析：
*A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal
Locality and Arrival Patterns*（IEEE IISWC 2012，未被当前 CCF 推荐目录收录）。
论文支持文件访问高度偏斜、明显 temporal locality 和大量 inactive storage；
详细原始比例与边界见
[SOURCES.md](SOURCES.md)。

本模型去掉全程不访问池，将其容量按论文原始活跃池比例重新分配，再按 2,400
个总单元做工程量化，得到 `100/100/100/2100` 单元，即约
`4.167/4.167/4.167/87.5%`。三个小池轮流成为热点，背景池始终保持访问。池内
Zipf(0.99) 是引用 YCSB 参数的受控实验设计，不是 Yahoo trace 的逐文件重放。

## 数据构造

| 数据池 | 单元 | 容量 | 参考 rank | 物理 bin |
|---|---:|---:|---:|---:|
| `pool_01` | 100 | 4.6875 GiB | 100 | 40 |
| `pool_02` | 100 | 4.6875 GiB | 100 | 40 |
| `pool_03` | 100 | 4.6875 GiB | 100 | 40 |
| `background` | 2,100 | 98.4375 GiB | 100 | 40 |

每个单元含 4 个 4 MiB、2 个 8 MiB 和 1 个 16 MiB 文件。每个固定大小档
独立计算 100 个参考 rank 的 Zipf(0.99)。前 20 个参考 rank 单独保留，后 80 个
每 4 个合并，形成 40 个物理 bin。小池头部/尾部 bin 分别为 1/4 单元，背景池
分别为 21/84 单元；bin 的访问权重等于其中参考 rank 权重之和。

## 正式阶段

| 时间 | 热点状态 |
|---:|---|
| 0–150 s | pool_01 85.41%，background 14.59% |
| 150–300 s | pool_02 85.41%，background 14.59% |
| 300–450 s | pool_03 85.41%，background 14.59% |
| 450–600 s | pool_01 复热 85.41%，background 14.59% |

热点在阶段边界直接切换。每阶段只访问当前热点池与 background；其他两个候选
热点池该阶段为 0%，但会在完整测试的其他阶段被访问。全部为 4 MiB 顺序读、
Direct I/O、`fwdrate=max`；600 秒总时长不变。第一和第四阶段引用同一套
`hot_pool_01*` FWD。每阶段单节点为 240 FWD，SYSU 为 400 FWD。

## 适用范围

适合观察小热点池迁移和复热；不运行 Hadoop，不模拟 HDFS block placement、
NameNode RPC 或作业计算。论文的 open/access 指标不能直接等同于 read bytes。

数据默认位于 `/mnt/cephfs/bigdata_mapreduce_vdbench_v1`。prepare 每批最多创建
20 个物理 bin，完成一次后可反复执行 `run_test.sh`。旧的 10-bin 数据目录不能
复用，切换本版本时需要重新执行 prepare。
