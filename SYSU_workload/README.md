# SYSU 12 节点 CephFS 冷热识别负载

本目录面向 12 个存储节点、每节点 1.8 TB SSD、三副本 CephFS。包含五个
Vdbench 负载和一个保留的 HPC IOR 负载。每个 Vdbench 负载的逻辑数据量为
750 GiB；HPC IOR 也使用独立的 750 GiB 数据集。单个实现三副本约占 2.25 TiB
原始空间；六个实现若全部同时保留，则为 4.5 TiB 逻辑数据、约 13.5 TiB 原始
副本空间，仍需另外预留 Ceph 运行余量。

## 与单节点版本的关系

两套 Vdbench 负载共享 `workload_common` 中的逻辑单元数、参考 rank、物理 bin、
Zipf(0.99) 权重算法和数据阶段。单节点版本保留纯读，主要用于较低风险地反复
验证冷热识别准确性：避免单盘/少 OSD 环境中的三副本写放大、后台恢复和写入
耐久化延迟干扰实验，也避免重复测试持续改写数据。SYSU 版本面向 12 节点正式
环境，在来源明确的应用生命周期阶段加入写操作，因此两套脚本不再只是容量
不同，正式 I/O 语义也不同。

两套版本的物理容量单元如下：

| 文件大小 | 每单元文件数 | 每档容量 |
|---:|---:|---:|
| 4 MiB | 16 | 64 MiB |
| 8 MiB | 8 | 64 MiB |
| 16 MiB | 4 | 64 MiB |
| 32 MiB | 2 | 64 MiB |
| 64 MiB | 1 | 64 MiB |

一个 SYSU 单元为 320 MiB；每负载 `2,400 × 320 MiB = 750 GiB`，共 74,400
个文件。MapReduce每池聚合到50个参考rank和20个物理bin，其他四种Vdbench
负载聚合到100个参考rank和40个物理bin；bin内文件由Vdbench随机选择，因此
实际执行的是分段Zipf近似。
不同文件大小不会改变该档容量份额。

## 负载一览

| 负载 | 逻辑结构 | 阶段与 I/O |
|---|---|---|
| MapReduce | 100/100/100/2100 单元；50 参考 rank → 20 bin/pool | `R → R → R → R`，4 × 150 s |
| GraphChi | 4 shard ×（100 参考 rank → 40 bin） | `R → R → R → R`，4 × 150 s |
| HPC Vdbench | 3 × 800 单元；100 → 40/group | `R → W → W → R`，4 × 150 s |
| AI 训练 | 2000/200/200 单元；100 → 40/group | `R → R → R → W → R`，160/160/160/60/60 s |
| AI 推理 | 3 × 800 单元；100 → 40/group | `W → R → W → R → R → R`，6 × 100 s |
| HPC IOR | WRF file-per-process，4 MPI rank | `R → W → W → R`，4 × 150 s |

写入只用于语义明确的 WRF checkpoint/history、AI 训练 checkpoint 和 KV cache
prefill。MapReduce 当前模拟论文 trace 的文件访问热度；GraphChi 论文支持
load/update/write 生命周期，但没有可直接映射为本模型的读写比例，因此两者
继续纯读，避免人为设定比例。所有 Vdbench 正式 I/O 均为 4 MiB Direct I/O、
`fwdrate=max`；prepare 按最多 20 个物理 bin 分批 clean/create，避免同时激活
全部 FSD。SYSU 配置故意不写 `hd=`，客户端定义由部署环境提供。热点在相邻 RD
之间直接切换，不生成中间渐变态；每个 Vdbench 负载仍为 600 秒。正式 run RD 使用
FWD 前缀通配符，避免 Vdbench 5.04.07 在大规模 FWD 显式列表上的 512 项解析
上限；每个通配符的匹配集合和 skew 总和均由统一验证器复核。五种 Vdbench
负载均为每阶段 200 FWD；MapReduce 复热复用已有读 FWD，HPC checkpoint 写入
和复热读取使用两套操作不同、权重相同的 FWD。

## 使用

先验证模型，再指定共享 CephFS 根目录：

```bash
cd /home/chris/ceph-test/SYSU_workload/<负载目录>
./validate_model.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/SYSU_workload ./run_test.sh
```

数据已创建后不要重复 prepare。详细来源和适用范围见各目录 README，以及
[`../new_workload/WORKLOAD_SUMMARY.md`](../new_workload/WORKLOAD_SUMMARY.md)。

修改模型或生成器后，在仓库根目录执行：

```bash
./SYSU_workload/validate_all.sh
```

该入口会以测试锚点重新渲染五个正式 Vdbench 负载，运行共享模型测试和 SYSU
部署测试、检查全部 shell 语法、验证 IOR，并用 Vdbench 5.04.07 的 `-s -e 2`
模式实际解析 10 份 prepare/run 配置。可通过 `VDBENCH_BIN` 覆盖工具路径。

[`hpc_wrf_ior_v1`](hpc_wrf_ior_v1/README.md) 保持独立实现，不使用混合文件
大小或 Zipf rank；其 WRF 生命周期与 Vdbench 版本一致采用 `R → W → W → R`。
