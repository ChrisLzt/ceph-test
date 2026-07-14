# SYSU 12 节点 Ceph 冷热识别负载

本目录面向 12 个 Ceph 存储节点、三副本 CephFS 环境，包含 **5 类应用、
6 个可执行实现**，也就是五种Vdbench负载和一个IOR负载；IOR 是 HPC 的
备选实现。
单节点版本保存在 [`../new_workload`](../new_workload/README.md)，两套脚本、
渲染结果和数据路径互不覆盖。

本套件用于冷热识别与性能开销实验，不用于提交 MapReduce、GraphChi、WRF、
MLPerf 或 vLLM 的标准 benchmark 成绩。

## 目标集群假设

- 12 个存储节点，每节点 1 块厂商标称 1.8 TB SSD，并作为 1 个 OSD 使用；
- CephFS data pool 使用三副本，即 `size=3`；
- 12 个 OSD 应位于 12 个不同的 `host` failure domain；
- 六套数据可以同时保留，但正式测试一次只运行一套负载；
- 若实际 OSD 数、设备容量、EC/副本策略或 failure domain 不同，必须重新
  计算容量并记录实际集群配置。

按厂商十进制容量计算，集群原始容量为 21.6 TB（约 19.64 TiB），三副本的
理论逻辑数据容量为 7.2 TB（约 6.55 TiB）。这些都是未扣除 Ceph 元数据、
空间分配和运行余量的理论值。

## 容量口径

- 文档中的 750 GiB 均指写入 CephFS 的**逻辑数据量**。
- 三副本下，每个 750 GiB 数据集对应 2,250 GiB（约 2.20 TiB）原始数据，
  未计元数据、BlueStore 和空间分配开销。
- 六个数据集若同时保留，逻辑容量为 4,500 GiB（约 4.39 TiB），三副本
  原始数据为 13,500 GiB（约 13.18 TiB）。
- 六套数据约占上述理论原始容量的 67%；实际比例以 `ceph df` 和最满 OSD
  为准，不能只用集群平均值判断余量。
- 造数前仍需根据 `ceph df`、池副本数和集群水位确认实际可用空间。

## 六个实现

| 类别 | 实现 | 容量结构 | 阶段 |
|---|---|---|---:|
| 大数据 | [MapReduce Vdbench](bigdata_mapreduce_vdbench_v1/README.md) | 30/30/30/660 GiB | 4 × 150 s |
| 图计算 | [GraphChi Vdbench](graph_graphchi_vdbench_v1/README.md) | 4 × 187.5 GiB | 5 × 120 s |
| HPC | [WRF Vdbench](hpc_wrf_vdbench_v1/README.md) | 3 × 250 GiB | 4 × 150 s |
| HPC 备选 | [WRF IOR](hpc_wrf_ior_v1/README.md) | 3 × 250 GiB | 4 × 150 s |
| AI 训练 | [训练数据与 checkpoint](ai_training_checkpoint_vdbench_v1/README.md) | 650 + 50 + 50 GiB | 3 × 160 s + 3 × 40 s |
| AI 推理 | [KV cache](ai_inference_kvcache_vdbench_v1/README.md) | 3 × 250 GiB | 6 × 100 s |

HPC Vdbench 与 IOR 是同一 WRF 文件生命周期的两种实现。Vdbench 提供明确的
组内 Zipf 冷热；IOR 保留 MPI rank 和 file-per-process 语义。两者用于不同
实验目的，不应把结果当作同一工具下的直接性能对照。

## Vdbench 的统一数据构造

5 个 Vdbench 负载均为 750 GiB、74,400 个文件。文件大小只取
4/8/16/32/64 MiB，各占 150 GiB，不使用 128 MiB 文件。

最小容量单元为 320 MiB：

| 文件大小 | 每单元文件数 | 每档容量 |
|---:|---:|---:|
| 4 MiB | 16 | 64 MiB |
| 8 MiB | 8 | 64 MiB |
| 16 MiB | 4 | 64 MiB |
| 32 MiB | 2 | 64 MiB |
| 64 MiB | 1 | 64 MiB |

一个单元共有 31 个文件。750 GiB 等于 2,400 个单元，因此共有
`2,400 × 31 = 74,400` 个文件。每个逻辑 pool、shard 或 rank 都按同样规则
拆为五档等容量文件；阶段权重再平均分到五档，避免文件大小改变逻辑热点比例。
这只保证各尺寸档的容量访问强度一致；小文件仍会带来更多文件选择和元数据
操作，因此混合文件大小本身仍是性能特征。五个负载使用相同尺寸分布，便于
控制这一变量。

统一 I/O 参数：

- 正式阶段全部为只读；造数据阶段负责 clean/create。
- 请求大小为 4 MiB，使用 Direct I/O。
- 默认 `THREADS=1`、`FWD_RATE=max`；均可通过环境变量覆盖。
- MapReduce、GraphChi、HPC Vdbench、AI checkpoint 和 AI prefill 使用
  文件内顺序读；AI 训练 dataset、AI decode 和 prefix reuse 使用随机读。
- 所有正式请求均为 4 MiB，因此在没有短 I/O 或错误的情况下，Vdbench 的
  operation share 也等于传输字节 share。

## 热点模型来源边界

- MapReduce 的 `85/1/1/13` 以 Yahoo MapReduce trace 的 temporal locality
  观测为基础；剩余比例分配和阶段轮换属于实验映射。
- GraphChi 的 `75/13/6/6` 来自当前 generated graph 与 PSW 推导流程，
  不是论文规定的通用常数。
- HPC Vdbench、AI 训练和 AI 推理采用对象级 Zipf(0.99) 聚合到 20 个
  等容量 rank；Zipf 是工程执行模型，不是应用论文实测比例。
- HPC IOR 只表达 startup/checkpoint/history 的组间生命周期，不提供组内
  Zipf，因此单阶段内同组的 4 个 rank 没有预设冷热差异。

更完整的论文来源见单节点各负载的 `SOURCES.md`，SYSU 文档只说明扩容映射，
不重复维护同一套引文。

## 客户端状态

当前 Vdbench 配置故意不包含 `hd=`：脚本尚未绑定 12 个客户端，Vdbench 会
在启动脚本的主机上发起 I/O。它可以访问 12 节点 Ceph 集群，但还不是
12 客户端并发模型。

IOR 固定 `NP=4`，通过可选的 `MPI_HOSTFILE` 决定 rank 放置。未提供 hostfile
时，4 个 rank 在本机启动。后续确定客户端后再增加 Vdbench `hd=` 渲染层，
IOR 继续使用 hostfile；数据布局和阶段模型无需改变。

正式多客户端配置确定前，应执行 `1 -> 2 -> 4 -> 8 -> 12` 客户端扩展测试，
确认单客户端没有限制集群吞吐。当前脚本尚未自动完成该步骤，也没有验证 I/O
客户端是否与 OSD 共置；这些条件必须记录在实验报告中。

## 使用方式

推荐共享 CephFS 根目录为 `/ceph-test/SYSU_workload`。每个脚本会在该根目录
下追加自身负载名，例如 MapReduce 数据写入：

```text
/ceph-test/SYSU_workload/bigdata_mapreduce_vdbench_v1
```

先验证全部模型；验证不会访问 CephFS，也不会运行正式负载：

```bash
cd /home/chris/ceph-test
SYSU_workload/validate_all.sh
```

单个 Vdbench 负载的基本流程：

```bash
cd /home/chris/ceph-test/SYSU_workload/<负载目录>
ANCHOR_ROOT=/ceph-test/SYSU_workload ./render_config.sh
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

`prepare_data.sh` 和 `run_test.sh` 都会按当前环境变量重新渲染配置，因此
手动执行 `render_config.sh` 主要用于预览。`rendered/` 含实际路径且不提交
Git。造数后重复测试只运行 `run_test.sh`，不要再次执行 prepare。

IOR 的入口相同，但多客户端运行时还需提供：

```bash
MPI_HOSTFILE=/path/to/hosts
```

每个分负载 README 给出精确数据布局、阶段访问对象和适用范围。

## 推荐测试顺序

1. 确认 data pool 为三副本、OSD 分布和 CephFS 挂载符合实验设计。
2. 执行 `validate_all.sh`，再逐套运行 `prepare_data.sh`；禁止并发造数。
3. 每次造数后等待所有 PG 恢复 `active+clean`，且无 recovery、backfill 或
   slow ops，再开始下一项。
4. 六套数据准备完成后，一次只运行一个 `run_test.sh`。
5. 比较冷热识别模块 OFF/ON 时，保持同一数据、客户端、速率和阶段参数；
   OFF/ON 各至少重复 3 次，并交错或随机运行顺序。
6. 每轮保存 Vdbench/IOR 输出、Ceph health、OSD/MDS 性能和冷热识别结果。

脚本本身不会自动关闭/开启冷热识别模块，也没有 Ceph 健康门禁和容量门禁；
这些仍由外层实验控制流程负责。

## 统计口径

六套数据同时存在时，运行一套负载会让其他五套数据保持静默。冷热识别结果
至少应同时给出两种口径：

- **活动负载口径**：只统计当前负载的 750 GiB 数据，评价阶段内热点和迁移；
- **全局口径**：统计整个 CephFS data pool，评价系统能否把其他静默数据保持
  为冷数据。

只报告全局准确率可能被大量静默数据主导，掩盖活动负载内部的误判；只报告
活动负载又无法反映全局冷数据管理，因此两者不能互相替代。

以下情况应将本轮标记为无效并重跑：OSD down/out、PG 非 `active+clean`、
发生 recovery/backfill、出现持续 slow ops、客户端或网络成为非预期瓶颈、
实际数据容量或阶段参数与记录不一致。
