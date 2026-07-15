# 文件级 Zipf Vdbench 负载设计

日期：2026-07-15

## 目标与范围

本设计统一调整以下两套测试中的五个 Vdbench 负载：

- `new_workload/`：单节点测试；
- `SYSU_workload/`：12 节点、三副本测试。

目标是在保留各负载应用层结构的前提下，让同一个 pool、window 或数据组内部
也具有可解释的文件级冷热差异。HPC IOR 版本保留现状，不应用混合文件大小或
Zipf rank。

本设计不使用 Vdbench Poisson 文件选择。所有文件热度都由 Zipf(0.99) 权重
计算并聚合到等容量 `heat_rank`；rank 内使用均匀文件选择。因此执行模型是
文件级 Zipf 的分段近似，而不是逐文件独立 FWD。

## 统一容量单元

单节点最小容量单元为 48 MiB：

| 文件大小 | 文件数 | 容量 |
|---:|---:|---:|
| 4 MiB | 4 | 16 MiB |
| 8 MiB | 2 | 16 MiB |
| 16 MiB | 1 | 16 MiB |

SYSU 最小容量单元为 320 MiB：

| 文件大小 | 文件数 | 容量 |
|---:|---:|---:|
| 4 MiB | 16 | 64 MiB |
| 8 MiB | 8 | 64 MiB |
| 16 MiB | 4 | 64 MiB |
| 32 MiB | 2 | 64 MiB |
| 64 MiB | 1 | 64 MiB |

两套环境均为每负载 2,400 个容量单元：

- 单节点：`2,400 × 48 MiB = 112.5 GiB`；
- SYSU：`2,400 × 320 MiB = 750 GiB`。

两套环境使用相同的逻辑组单元数、rank 数和每 rank 单元数；物理容量按
`320 / 48 = 6.6667` 倍缩放。

## 文件级 Zipf 聚合

每个逻辑组的每个文件大小档独立生成 Zipf(0.99)。对包含 `N` 个文件的固定
大小档，文件 `i` 的归一化权重为：

\[
p_i=\frac{i^{-0.99}}{\sum_{k=1}^{N}k^{-0.99}}
\]

文件按序号连续、等数量地划分到 `R` 个等容量 rank。大小档 `s` 中 rank `r`
的权重为：

\[
Z_{s,r}=\sum_{i\in rank(s,r)}p_i
\]

阶段中逻辑组 `g` 的访问份额为 `G_g`，文件大小档数量为 `K`，对应 FWD 的
最终份额为：

\[
W_{g,s,r}=G_g\times\frac{1}{K}\times Z_{s,r}
\]

所有 FWD 权重使用十进制小数并保持总和为 100%。禁止使用“每个 rank 至少
1%”的整数归一化，因为这会破坏 Zipf 长尾。rank 内使用
`fileselect=random`；`fileio` 继续表达文件内部顺序或随机读取。

Zipf 给所有文件非零理论概率，但固定时长测试不能保证每个长尾文件都实际被
选择。验证脚本检查概率、容量和配置结构，不把“每文件至少一次访问”作为静态
保证。

## MapReduce

### 数据结构

| 数据池 | 单元数 | 容量占比 | rank 数 | 每 rank 单元 |
|---|---:|---:|---:|---:|
| `pool_01` | 96 | 4% | 32 | 3 |
| `pool_02` | 96 | 4% | 32 | 3 |
| `pool_03` | 96 | 4% | 32 | 3 |
| `background` | 2,112 | 88% | 32 | 66 |

单节点容量为 `4.5 + 4.5 + 4.5 + 99 = 112.5 GiB`；SYSU 容量为
`30 + 30 + 30 + 660 = 750 GiB`。

### 阶段

保留四个 150 秒阶段和 `85/1/1/13` 的 pool 级访问比例：

1. `pool_01` 为 85% 热点；
2. `pool_02` 为 85% 热点；
3. `pool_03` 为 85% 热点；
4. `pool_01` 复热。

每个 pool 的阶段份额再按内部 32 个 Zipf rank 和文件大小档拆分。MapReduce
论文支持 pool 容量与 open/temporal-locality 层面的比例；pool 内 Zipf(0.99)
是引用 YCSB 分布的受控实验参数，不宣称为论文实测。

## GraphChi

### 4 shard × 4 window

图被划分为四个目标 interval/shard。每个 shard 按源 interval 再分为四个
window，共 16 个等容量 window。`window_src_dst` 表示源 interval 为 `src`、
目标 interval 为 `dst` 的边集合，并存储在 `shard_dst` 中。

| 层级 | 数量 | 每项单元 | 单节点容量 | SYSU 容量 |
|---|---:|---:|---:|---:|
| shard | 4 | 600 | 28.125 GiB | 187.5 GiB |
| window/shard | 4 | 150 | 7.03125 GiB | 46.875 GiB |
| rank/window | 15 | 10 | 480 MiB | 3.125 GiB |

全图共有 `4 × 4 × 15 = 240` 个 window-rank。

### PSW 阶段

四个阶段各运行 150 秒。阶段 `p`：

- 读取目标 shard `p` 的全部四个 window；
- 从其他三个 shard 各读取源 interval 为 `p` 的一个 sliding window。

每阶段共有七个活动 window。等容量模型下，每个活动 window 承担阶段访问的
`1/7`，再在 window 内部按 15 个 Zipf rank 和文件大小档拆分。每阶段活动
rank 为 `7 × 15 = 105`。

四阶段后，对角 window 被访问一次，非对角 window 作为 memory-shard window
和 sliding window 各被访问一次。GraphChi 论文支持 PSW 的 shard/window 与
访问流程；window 等容量和 window 内 Zipf 是受控实验参数。

## HPC Vdbench

| 数据组 | 单元数 | rank 数 | 每 rank 单元 |
|---|---:|---:|---:|
| `startup` | 800 | 80 | 10 |
| `checkpoint` | 800 | 80 | 10 |
| `history` | 800 | 80 | 10 |

四个 150 秒阶段保持 `startup → checkpoint → history → checkpoint_reheat`。
每阶段只活动一个数据组的 80 个 Zipf rank。正式阶段保持纯顺序读、4 MiB
请求和 Direct I/O。

## AI 训练

| 数据组 | 单元数 | rank 数 | 每 rank 单元 |
|---|---:|---:|---:|
| `dataset` | 2,080 | 80 | 26 |
| `checkpoint_current` | 160 | 80 | 2 |
| `checkpoint_old` | 160 | 80 | 2 |

总容量比例为 `13:1:1`。阶段保持 `160 × 3 + 40 × 3 = 600` 秒：

- 三个 dataset epoch 各 160 秒，随机读，Zipf 头部分别位于 rank 01、02、03；
- current checkpoint 两次各 40 秒，顺序读；
- old checkpoint recovery 40 秒，顺序读。

每阶段活动对应数据组的 80 个 Zipf rank。dataset 热点随 epoch 轮换；
checkpoint current 保留重复访问，old 只在恢复阶段活动。

## AI 推理

| 数据组 | 单元数 | rank 数 | 每 rank 单元 |
|---|---:|---:|---:|
| `kv_active` | 800 | 80 | 10 |
| `kv_next` | 800 | 80 | 10 |
| `kv_prefix` | 800 | 80 | 10 |

六个阶段各 100 秒，每阶段只活动一个数据组的 80 个 Zipf rank：

- active prefill：顺序读；
- active decode：随机读；
- next prefill：顺序读；
- next decode：随机读；
- prefix reuse primary：随机读，Zipf 头部位于 rank 01；
- prefix reuse shifted：随机读，Zipf 头部移到 rank 02。

## FWD 规模与造数据批次

| 负载 | 单节点每阶段活动 FWD | SYSU 每阶段活动 FWD |
|---|---:|---:|
| MapReduce | 384 | 640 |
| GraphChi | 315 | 525 |
| HPC | 240 | 400 |
| AI 训练 | 240 | 400 |
| AI 推理 | 240 | 400 |

prepare 不得把一个负载的全部 FSD 同时作为活动 FWD。生成器按最多 20 个
rank 一批依次输出 clean/create RD；单节点每批至多 60 个 FWD，SYSU 每批
至多 100 个 FWD。prepare 和正式测试继续分离，重复测试不重新造数据。

## 工具参数

- 正式 Vdbench 阶段全部只读；
- `xfersize=4m`；
- `fwdrate=max`；
- Direct I/O；
- `fileselect=random`，不使用 Poisson；
- MapReduce、GraphChi、HPC、AI checkpoint、AI prefill 使用顺序读；
- AI dataset、AI decode 和 prefix reuse 使用随机读；
- SYSU 的 `hd=` 定义继续留空，由部署时提供。

## 验证要求

每个负载的验证脚本必须检查：

1. 总容量、逻辑组容量和文件大小集合；
2. 单元数、rank 数和每 rank 单元数可整除；
3. 每个 rank 的各大小档容量相同；
4. Zipf 原始权重为正，聚合后小数权重不被整数化；
5. 每个阶段 FWD 权重总和在数值容差内等于 100%；
6. 阶段数量、阶段时长、顺序/随机读和活动数据组符合本文；
7. `prepare_data.vdb` 采用分批 clean/create；
8. 单节点与 SYSU 使用相同逻辑单元布局；
9. IOR 文件和脚本没有被修改。

## 来源边界

- MapReduce 保留论文推导的容量与 temporal-locality pool 比例；
- GraphChi 保留论文的 Parallel Sliding Windows、shard 与 window 访问结构；
- HPC 保留 WRF startup/checkpoint/history 文件生命周期；
- AI 训练保留 dataset epoch 与 checkpoint/recovery 生命周期；
- AI 推理保留 prefill/decode/prefix-reuse 生命周期；
- Zipf(0.99) 来源于 YCSB 常用 key popularity 模型，是统一的受控文件热度
  参数，不是上述应用论文给出的文件级 trace 比例。
