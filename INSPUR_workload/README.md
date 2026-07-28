# INSPUR 150 TiB CephFS 冷热识别负载

本目录面向原始总容量上限 150 TiB、三副本的 CephFS。包含五个 Vdbench
负载和一个 HPC IOR 负载。它复用 SYSU 的 2,400 个逻辑单元、rank/bin、
Zipf(0.99)、阶段时长和读写语义，只把五档文件大小整体扩大四倍。

## 容量预算

| 项目 | 容量 |
|---|---:|
| 单个负载 | 3000 GiB（2.9297 TiB） |
| 六个负载逻辑合计 | 18000 GiB（17.5781 TiB） |
| 三副本原始占用 | 54000 GiB（52.7344 TiB） |
| 150 TiB 中剩余原始容量 | 约 97.266 TiB |
| 原始容量使用率 | 约 35.2% |

六套数据可以同时保留。剩余约 64.8% 原始空间用于 Ceph 元数据、BlueStore、
回填、恢复和性能余量，不应再按“50 TiB 逻辑容量全部可用于测试数据”规划。

## Vdbench 文件布局

| 文件大小 | 每单元文件数 | 每档容量 |
|---:|---:|---:|
| 16 MiB | 16 | 256 MiB |
| 32 MiB | 8 | 256 MiB |
| 64 MiB | 4 | 256 MiB |
| 128 MiB | 2 | 256 MiB |
| 256 MiB | 1 | 256 MiB |

一个单元为 1280 MiB（1.25 GiB），所以每个 Vdbench 负载为
`2,400 × 1.25 GiB = 3000 GiB`。文件数仍为每负载 74,400 个；扩大的是文件
容量，不是 FSD、rank、bin 或文件数量。

## 六种负载

| 负载 | 数据结构 | 阶段与 I/O |
|---|---|---|
| MapReduce | 125/125/125/2625 GiB；50 rank → 20 bin/pool | `R → R → R → R`，4 × 150 s |
| GraphChi | 4 shard × 750 GiB；100 rank → 40 bin/shard | `R → R → R → R`，4 × 150 s |
| HPC Vdbench | startup/checkpoint/history 各 1000 GiB | `R → W → W → R`，4 × 150 s |
| AI 训练 | dataset 2500 GiB；current/old 各 250 GiB | `R → R → R → W → R`，160/160/160/60/60 s |
| AI 推理 | active/next/prefix 各 1000 GiB | `W → R → W → R → R → R`，6 × 100 s |
| HPC IOR | 三组各 1000 GiB；4 MPI rank/group | `R → W → W → R`，4 × 150 s |

写入只用于语义明确的 WRF checkpoint/history、AI 训练 checkpoint 和 KV
cache prefill。MapReduce 与 GraphChi 保持读取模型，不人为增加没有明确比例
来源的写流量。五种 Vdbench 均使用 4 MiB Direct I/O 和 `fwdrate=max`；
文件变大不改变单次 I/O 大小。

## FWD 约束

MapReduce 每个活动热点池和 background 各 100 FWD；其他 Vdbench 每个活动组
为 `40 bin × 5 size = 200 FWD`。因此所有正式 RD 都只匹配 200 FWD，低于
Vdbench 5.04.07 的 512 项限制。配置使用 FWD 前缀通配符，总 FWD 定义数超过
512 不会形成单个 RD 的显式列表超限。

## 使用

修改模型或部署前先执行统一验证：

```bash
cd /home/chris/ceph-test
./INSPUR_workload/validate_all.sh
```

各负载的常规流程：

```bash
cd /home/chris/ceph-test/INSPUR_workload/<负载目录>
./validate_model.sh
ANCHOR_ROOT=/ceph-test/INSPUR_workload ./prepare_data.sh
ANCHOR_ROOT=/ceph-test/INSPUR_workload ./run_test.sh
```

数据已经创建后不要重复 prepare。INSPUR Vdbench 配置不包含 `hd=`，客户端由
部署环境提供。详细来源与阶段边界见各负载 README 和
[`../new_workload/WORKLOAD_SUMMARY.md`](../new_workload/WORKLOAD_SUMMARY.md)。
