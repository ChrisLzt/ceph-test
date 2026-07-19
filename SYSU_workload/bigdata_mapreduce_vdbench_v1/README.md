# SYSU MapReduce 文件冷热负载

这是单节点 MapReduce 模型的 750 GiB 物理版本。来源、论文比例和适用范围见
[`../../new_workload/bigdata_mapreduce_vdbench_v1/README.md`](../../new_workload/bigdata_mapreduce_vdbench_v1/README.md)。

| 数据池 | 单元 | 容量 | 参考 rank | 物理 bin |
|---|---:|---:|---:|---:|
| `pool_01` | 100 | 31.25 GiB | 100 | 40 |
| `pool_02` | 100 | 31.25 GiB | 100 | 40 |
| `pool_03` | 100 | 31.25 GiB | 100 | 40 |
| `background` | 2,100 | 656.25 GiB | 100 | 40 |

四个 150 秒阶段依次以 pool_01、pool_02、pool_03、pool_01 为当前热点池。
每阶段只访问当前热点池 85.41% 和 background 14.59%，另外两个小池为 0%。
每个 pool 的 4/8/16/32/64 MiB 固定大小档内部先计算 100 个参考 rank 的
Zipf(0.99)：前20个单独保留，后80个每4个合并，形成40个物理bin。小池
头部/尾部bin分别为0.3125/1.25 GiB，background分别为6.5625/26.25 GiB。
每阶段400 FWD；第一和第四阶段复用一套FWD。全部为4 MiB Direct I/O、
`fwdrate=max`，总时长仍为600秒。

数据目录为 `$ANCHOR_ROOT/bigdata_mapreduce_vdbench_v1`；配置不包含 `hd=`。
