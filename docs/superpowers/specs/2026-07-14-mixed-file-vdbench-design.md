# 五种 Vdbench 负载混合文件大小设计

## 目标

将五种 Vdbench 负载统一扩展到 750 GiB，并让每个负载同时包含
4、8、16、32、64 MiB 文件。文件大小分布与冷热分布彼此独立：

- 每种文件大小在任一逻辑池、shard 或 rank 中占相同容量；
- 所有正式 I/O 继续固定为 4 MiB Direct I/O；
- MapReduce 保留 Yahoo! 论文派生的池级比例；
- GraphChi 保留 generated graph 经 PSW 规则派生的 shard 比例；
- HPC、AI 训练和 AI 推理在等容量 rank 上使用 Zipf(0.99)；
- 不引入全程不访问的数据。

本设计新建五种 Vdbench 的 12 节点版本，不修改单节点目录
`/home/chris/ceph-test/SINGLE_workload`，也不修改其中的 `hpc_wrf_ior_v1`。

## 源码与数据路径

12 节点、三副本版本统一放在仓库的新目录：

```text
/home/chris/ceph-test/SYSU_workload
```

该目录与 `SINGLE_workload` 并列；`SINGLE_workload` 继续作为单节点版本，不复用
12 节点渲染结果。五个负载沿用现有负载名称作为 `SYSU_workload` 下的子目录。

CephFS 在 12 个客户端上的实际挂载点不由源码目录推断。渲染时统一通过
`ANCHOR_ROOT` 指定共享 CephFS 数据根目录，再追加负载名称。所有客户端必须
以相同绝对路径挂载该目录。`prepare_data.sh` 只创建
`${ANCHOR_ROOT}/<负载名>`，不得创建或写入源码目录。

当前版本先不配置客户端，不生成任何 `hd=` 行。Vdbench 参数文件保持本地执行
语义，用于先验证容量、阶段和 skew。后续获得客户端清单后，另行增加 12 客户端
`hd=` 渲染层；本次不得硬编码主机名、SSH 用户或远端 Vdbench 路径。

## 统一容量单元

以 4 MiB Ceph 对象为归一化单位。一个 320 MiB 容量单元由下列文件组成：

| 文件大小 | 文件数 | 容量 |
|---:|---:|---:|
| 4 MiB | 16 | 64 MiB |
| 8 MiB | 8 | 64 MiB |
| 16 MiB | 4 | 64 MiB |
| 32 MiB | 2 | 64 MiB |
| 64 MiB | 1 | 64 MiB |
| 合计 | 31 | 320 MiB |

750 GiB 等于 2400 个容量单元，共 74,400 个文件。容量单元只是生成配置时的
记账概念，不创建 `unit_*` 目录。

每个逻辑 rank 按五个独立 size bucket 建模。每个 bucket 使用独立 FSD，以便
精确控制文件数和容量；rank 的访问权重再平均分配给五个等容量 bucket。实现可由
脚本生成大量 FSD/FWD，禁止手工维护展开后的重复配置。

## MapReduce

容量继续使用 4% / 4% / 4% / 88%：

| 数据池 | 容量 | 容量单元 |
|---|---:|---:|
| `pool_01` | 30 GiB | 96 |
| `pool_02` | 30 GiB | 96 |
| `pool_03` | 30 GiB | 96 |
| `pool_04` | 660 GiB | 2112 |

前三个池每种大小分别有 1536/768/384/192/96 个文件；背景池分别有
33792/16896/8448/4224/2112 个文件。

正式阶段继续使用 85/1/1/13，并在 A、B、C 之间迁移和复热。每个池的阶段权重
平均分给五个 size bucket。例如 85% 池的每个 bucket 得到 17%，13% 池的每个
bucket 得到 2.6%。不向 MapReduce 叠加 Zipf。

## GraphChi

四个 shard 各 187.5 GiB，即每个 shard 600 个容量单元。每个 shard 的五个
size bucket 各 37.5 GiB，文件数分别为 9600/4800/2400/1200/600。

正式阶段继续由 generated graph 和 GraphChi PSW 规则派生 shard 权重。当前
整数化权重为 75/13/6/6，分别平均分给对应 shard 的五个 size bucket。不得在
shard 内额外叠加 Zipf，因为这会加入 GraphChi 来源未提供的文件流行度模型。

## HPC WRF Vdbench

`startup`、`checkpoint`、`history` 三组各 250 GiB。每组包含 20 个等容量 rank，
每 rank 为 12.5 GiB、40 个容量单元。每 rank 的五个 bucket 各 2.5 GiB，文件数
分别为 640/320/160/80/40。

每组等价为 64,000 个 4 MiB 对象。按 Zipf(0.99) 聚合到 20 个等容量 rank，
重新计算后的整数权重为：

```text
73 / 6 / 3 / 2 / 1 x 16
```

四阶段生命周期保持 startup、checkpoint、history、checkpoint reheat，不改变
纯读、4 MiB、Direct I/O 约束。

## AI 训练

为接近当前 dataset/checkpoint 容量关系并满足容量单元整除，使用：

| 数据组 | 容量 | 容量单元 |
|---|---:|---:|
| dataset | 650 GiB | 2080 |
| checkpoint_current | 50 GiB | 160 |
| checkpoint_old | 50 GiB | 160 |

dataset 包含 20 个 32.5 GiB rank，每 rank 104 个容量单元。每 rank 的五个
bucket 各 6.5 GiB，文件数为 1664/832/416/208/104。

dataset 等价为 166,400 个 4 MiB 对象。Zipf(0.99) 聚合权重重新计算为：

```text
74 / 5 / 3 / 2 / 1 x 16
```

三个 dataset epoch 继续旋转最高权重 rank。两个 checkpoint 组各按五种大小
等容量拆分，每种 10 GiB、文件数 2560/1280/640/320/160。checkpoint 阶段不
使用 Zipf，每种 size bucket 获得 20% 操作，保留 current 重读和 old recovery。

## AI 推理

`kv_active`、`kv_next`、`kv_prefix` 三组各 250 GiB。每组包含 20 个 12.5 GiB
rank，rank 内文件构成与 HPC 相同：640/320/160/80/40。

每组使用 64,000 个 4 MiB 等价对象推导 Zipf(0.99)，rank 权重为：

```text
73 / 6 / 3 / 2 / 1 x 16
```

保留 active、next、prefix 生命周期以及既有热点迁移；prefill 继续顺序读，
decode 和 prefix 继续随机读。文件大小分布不参与热点轮换。

## Vdbench 映射约束

- 五档 size bucket 使用独立 FSD，目录命名为 `size_4m` 到 `size_64m`。
- 所有 `ANCHOR` 由 `${ANCHOR_ROOT}/<负载名>` 得到，渲染前必须提供
  `ANCHOR_ROOT`；禁止回退到单节点版 `/mnt/cephfs/<负载名>`。
- 当前生成配置不包含 `hd=`；客户端分配不在本次范围。
- rank/pool/shard 的总权重在五个等容量 bucket 间平均分配。
- `skew` 允许使用小数；每个正式 FWD 权重必须大于零，总和必须为 100。
- `xfersize=4m`、`openflags=o_direct`。
- 造数据配置只包含 clean/create，正式配置不得包含 `format=`。
- 所有展开配置由生成脚本产生，验证脚本检查容量、文件数、skew 和阶段引用。
- 若 CephFS 实际 object size 不是 4 MiB，必须停止并重新计算 Zipf 对象数量。

## 验收条件

1. 每个负载总容量精确为 750 GiB、总文件数为 74,400。
2. 每个逻辑池、shard 或 rank 内五档文件各占 20% 容量。
3. MapReduce 和 GraphChi 的来源比例未被 Zipf 覆盖。
4. HPC、AI dataset/KV 的 Zipf 权重与新的对象总数一致，所有 rank 非零访问。
5. 五种正式负载均保持 4 MiB Direct I/O，阶段数和阶段时长不因文件大小调整而改变。
6. 各负载的模型验证和生成器单元测试全部通过。

## 不在本次范围

- 不在任何 CephFS 挂载点造数据，也不执行正式测试。
- 不修改 HPC IOR 负载。
- 不修改或覆盖 `SINGLE_workload` 中的单节点脚本和渲染结果。
- 不把 320 MiB 容量单元解释为应用真实文件格式。
- 不宣称 Zipf(0.99) 是 WRF、MLPerf 或 PagedAttention 论文给出的实测比例。
