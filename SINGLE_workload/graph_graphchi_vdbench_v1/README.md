# GraphChi shard 内 Zipf 冷热负载

## 来源与设计逻辑

应用语义来源于 Kyrola、Blelloch、Guestrin 的 *GraphChi: Large-Scale Graph
Computation on Just a PC*（OSDI 2012，CCF-A）。GraphChi 把图划分为 shard，
并按顶点 interval 顺序处理。详细来源边界见 [SOURCES.md](SOURCES.md)。

为了让单个阶段具有明确、可控且不超过 512 FWD 的文件热度，本版本不再实现
Parallel Sliding Windows，也不再构造 `window_srcXX_dstYY`。它保留“shard 顺序
处理”这一上层生命周期，并在每个 shard 内使用 Zipf(0.99) rank 分布。shard
等容量、100 个参考 rank、40 个物理 bin 和 Zipf 参数都是受控实验参数，不是
GraphChi 论文测量值。

## 数据构造

- 4 个等容量 shard，每个 600 单元、28.125 GiB；
- 每个 shard 以 100 个参考 rank 计算 Zipf，压缩为 40 个物理 bin；
- 前 20 个 bin 各对应 1 个参考 rank，即 6 单元、288 MiB；
- 后 20 个 bin 各合并 4 个参考 rank，即 24 单元、1.125 GiB；
- 总计 160 个物理 bin、2,400 单元、112.5 GiB。

每个 shard 的三个固定大小档分别计算 100 个参考 rank 的 Zipf(0.99)，再按
上述规则聚合到 40 个物理 bin。因此一个阶段有
`40 × 3 = 120` 个FWD，bin 1最热，长尾bin仍有非零理论访问概率。

## 正式阶段

四个逻辑阶段依次处理 shard 00、01、02、03，每个占150秒预算：

| 时间 | 热点状态 |
|---:|---|
| 0–150 s | shard 00内部Zipf读 |
| 150–300 s | shard 01内部Zipf读 |
| 300–450 s | shard 02内部Zipf读 |
| 450–600 s | shard 03内部Zipf读 |

每个阶段只读取当前shard，热点在边界直接切换。每阶段120 FWD。全部为
4 MiB顺序读、Direct I/O、`fwdrate=max`，合计600秒。完整测试中
四个shard都会被访问，但不再设置shard 0复热。

## 数据迁移

旧版`window_src*`数据与当前布局不兼容。首次重新造数据时，`prepare_data.sh`
会在该负载的shard目录下删除旧window目录，再创建新的`shard/rank/size`结构。

## 适用范围

适合观察shard级热点迁移和shard内部文件热度；不执行GraphChi、PageRank、顶点
更新、message passing、收敛判断、PSW sliding window或GraphChi原生shard编码。

数据默认位于`/mnt/cephfs/graph_graphchi_vdbench_v1`。
