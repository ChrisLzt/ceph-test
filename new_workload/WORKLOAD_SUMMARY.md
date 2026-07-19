# 五类冷热识别负载来源与设计摘要

五个单节点正式负载均为 112.5 GiB、600 秒、纯读 Vdbench 模型。统一采用
4/8/16 MiB 混合文件，以及聚合到参考 rank 和物理 bin 的分段 Zipf(0.99)
热度近似；不同负载的区别来自论文或官方系统所支持的数据生命周期与阶段访问方式。

项目资料中的四份场景需求报告还给出了面向性能测试的读写、请求大小和工具选型，
但与当前纯读冷热识别目标并不等价。逐项对照见
[STORAGE_SCENE_PDF_ANALYSIS.md](STORAGE_SCENE_PDF_ANALYSIS.md)。

## 1. MapReduce

- 来源：Abad 等，*A Storage-Centric Analysis of MapReduce Workloads: File
  Popularity, Temporal Locality and Arrival Patterns*，IEEE IISWC 2012
  （未被当前 CCF 推荐目录收录）；分析 Yahoo! Hadoop/MapReduce 生产 trace。
- 设计：三个候选热点池各 100 单元，背景池 2,100 单元，容量占比约
  `4.167/4.167/4.167/87.5%`。每池以 100 个参考 rank 计算 Zipf，前 20 个
  单独保留，后 80 个每 4 个合并，最终形成 40 个物理 bin。
- 阶段：`pool_01 → pool_02 → pool_03 → pool_01`，每阶段 150 秒，pool 访问
  份额为当前热点池 `85.41%`、background `14.59%`；另外两个小池为 0%，
  边界直接切换。
- 适用范围：论文支持文件流行度和 temporal locality；池内 Zipf、阶段缩放与
  4 MiB 请求是实验参数，open 次数不能直接解释为 read bytes。

## 2. GraphChi

- 来源：Kyrola、Blelloch、Guestrin，*GraphChi: Large-Scale Graph
  Computation on Just a PC*，OSDI 2012（CCF-A）。
- 设计：四个等容量 shard，每个 600 单元；每个固定大小档先按 100 个参考
  rank 计算 Zipf，前 20 个单独保留、后 80 个每 4 个合并为 20 个尾部 bin，
  共 40 个物理 bin；不再构造 window。
- 阶段：依次处理 shard 0、1、2、3，每阶段 150 秒，只访问当前 shard，边界
  直接切换。
- 适用范围：仅保留 GraphChi 的 shard/interval 顺序处理作为生命周期来源，
  不实现 Parallel Sliding Windows、PageRank、顶点更新或原生文件格式。

## 3. HPC / WRF

- 来源：NSF NCAR/MMM WRF 的输入/边界、restart/checkpoint、history/output
  文件生命周期；另保留 IOR 实现表达 MPI 并行 I/O。
- 设计：startup、checkpoint、history 各 800 单元，以 100 个参考 rank 计算
  Zipf 并压缩为 40 个物理 bin；活动组内部按 Zipf 分配。
- 阶段：`startup → checkpoint → history → checkpoint_reheat`。前三阶段为
  直接切换，每阶段 150 秒，最后阶段重新读取 checkpoint。
- 适用范围：Vdbench 版用于明确的阶段内冷热，不模拟 NetCDF/HDF5、MPI
  collective I/O 或 WRF 计算；需要并行文件语义时使用保留的 IOR 版。

## 4. AI 训练

- 来源：Meta DSI，*Understanding Data Storage and Ingestion for Large-Scale
  Deep Recommendation Model Training*，ISCA 2022（CCF-A）；checkpoint 生命周期
  参考 MLPerf Storage/DLIO。
- 设计：dataset/current checkpoint/old checkpoint 为 `2000/200/200` 单元，
  即 `10:1:1`。每组均以 100 个参考 rank 计算 Zipf，再压缩为 40 个物理 bin；
  dataset 每个头部 bin 为 20 单元，checkpoint 每个头部 bin 为 2 单元。
- 阶段：三个 dataset epoch 各 160 秒，Zipf 头依次为 rank 1、2、3；随后
  current checkpoint 和 old checkpoint 各顺序读 60 秒。各边界直接切换。
- 适用范围：保留训练数据重复读取、热点迁移和 checkpoint 恢复语义，不运行
  模型，也不声称 Zipf 是 Meta trace 的实测比例。

## 5. AI 推理

- 来源：vLLM/PagedAttention，*Efficient Memory Management for Large
  Language Model Serving with PagedAttention*，SOSP 2023（CCF-A）；存储分类
  参考 MLPerf Storage KV Cache。
- 设计：kv_active、kv_next、kv_prefix 各 800 单元；每组以 100 个参考 rank
  计算 Zipf，再压缩为 40 个物理 bin。
- 阶段：active prefill/decode、next prefill/decode、prefix primary/shifted，
  六个阶段各 100 秒。active 与 next 的 prefill/decode 均保持各自 rank 1
  最热，prefix primary 为 rank 1 最热，shifted 为 rank 2 最热；边界直接切换。
- 适用范围：表达 KV cache 使用、切换与 prefix reuse，不运行 LLM，也不评价
  token 吞吐；正式模型读取预生成 KV 文件，不模拟 prefill 写入。

## 统一边界

Vdbench 只是把上述模型映射到 CephFS。所有容量、文件大小、参考rank/bin数、600秒
预算和 Zipf(0.99) 都是可复现的实验控制参数。来源只用于支持“为什么访问这些
数据、为什么有这些阶段”，不能把结果宣称为原应用或标准 benchmark 成绩。
每个正式 RD 展开通配符后最多匹配 512 个 FWD；MapReduce 单节点/SYSU 每阶段
分别为 240/400，其他四种负载分别为 120/200。MapReduce 第一/第四阶段与 HPC
第二/第四阶段分别复用同一 FWD 集合。直接切换使每个 RD 都对应一个明确热点状态。
