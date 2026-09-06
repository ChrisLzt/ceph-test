# INSPUR CephFS 冷热识别负载

本目录包含 5 个 Vdbench 负载和 1 个 HPC IOR 负载，用于在 CephFS 上生成
来源可追溯、阶段边界明确的冷热访问。各负载以应用的数据组织和生命周期为
设计依据，重点观察热点识别、迁移与复热，不用于复现原生应用的计算性能。

## 容量

| 负载 | 逻辑容量 |
|---|---:|
| MapReduce | 3000 GiB（2.9297 TiB） |
| GraphChi | 3000 GiB（2.9297 TiB） |
| HPC Vdbench | 3000 GiB（2.9297 TiB） |
| AI 训练 | 3000 GiB（2.9297 TiB） |
| AI 推理 | 3000 GiB（2.9297 TiB） |
| HPC IOR | 3000 GiB（2.9297 TiB） |
| 六种负载合计 | 18000 GiB（17.5781 TiB） |

六种数据全部保留且使用三副本时，原始副本容量约为 54000 GiB
（52.7344 TiB）。除此之外还应为文件系统元数据、回填、恢复和运行期间的
空间波动预留容量。

## 整体设计

五个 Vdbench 负载都在所属数据组内部构造文件级访问偏斜。文件访问概率先按
Zipf 分布计算，再聚合为可由 Vdbench 执行的数据区间；因此既保留高频头部和
低频长尾，也避免为每个文件分别创建工作定义。热点在阶段边界切换，各负载的
正式测试总时长均为 600 秒。

### MapReduce

依据 Yahoo! MapReduce 生产 trace 中的文件流行度和时间局部性设计。三个候选
热点池依次成为当前热点，最后重新访问第一个热点池；大容量 background 在每个
阶段都以较低份额持续访问。当前热点池与 background 内部都具有文件级冷热差异，
用于同时观察池间热点迁移和池内文件热度。

### GraphChi

依据 GraphChi 的 Parallel Sliding Windows 思路，将图数据划分为四个 shard。
四个阶段依次访问不同 shard，表示图处理窗口沿分片移动；每个 shard 内部仍有
文件级访问偏斜，用于区分分片级热点和分片内部热点。

### HPC Vdbench

依据 WRF 的输入、checkpoint 和 history 文件生命周期组织数据。测试依次处理
startup、checkpoint、history，并在最后重新访问 checkpoint，形成一次明确的
复热。正式读写版本将 checkpoint 和 history 表示为写入阶段，startup 与
checkpoint 复热表示为读取阶段。

### AI 训练

数据划分为训练 dataset、当前 checkpoint 和旧 checkpoint。前三个阶段表示连续
epoch 对训练数据的读取，并移动 dataset 内部的最热区域；随后写入当前
checkpoint，再读取旧 checkpoint 模拟恢复。该设计用于区分长期反复访问的训练
数据和短时活跃的状态文件。

### AI 推理

数据划分为 active KV cache、next KV cache 和可复用 prefix。active 与 next
分别经历 prefill 和 decode，随后两次访问 prefix，并在第二次改变其内部热点。
prefill 表示缓存写入，decode 和 prefix reuse 表示读取，从而形成写入、随机访问
和前缀复用相结合的阶段序列。

### HPC IOR

IOR 版本与 HPC Vdbench 采用相同的 startup、checkpoint、history 和 checkpoint
复热生命周期，但保留 MPI 并行进程和 file-per-process 语义。它不使用文件级
Zipf 分布，主要作为更接近 HPC 并行文件访问方式的替代表示；两种 HPC 数据集
相互独立。

## 读写范围

写入只用于语义明确的 WRF checkpoint/history、AI 训练 checkpoint 和 KV cache
prefill。MapReduce 和 GraphChi 保持读取模型，避免加入缺少明确来源的写入比例。
各负载的论文来源、阶段映射和适用范围见对应目录的 `README.md` 与 `SOURCES.md`。

## 基本流程

每个负载目录分别提供配置生成、模型验证、数据准备和正式测试入口。数据准备
完成后可以重复运行正式测试，不需要每次重新造数据。修改模型或部署配置后，可在
仓库根目录执行：

```bash
./INSPUR_workload/validate_all.sh
```

各负载的具体环境变量和执行方式见其目录内的 `README.md`。
