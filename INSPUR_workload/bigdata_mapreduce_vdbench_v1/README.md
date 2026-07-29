# INSPUR MapReduce 文件冷热负载

这是 INSPUR 套件中 3000 GiB 的 MapReduce 物理版本。来源、论文比例和适用范围见
[`../../SINGLE_workload/bigdata_mapreduce_vdbench_v1/README.md`](../../SINGLE_workload/bigdata_mapreduce_vdbench_v1/README.md)。

| 数据池 | 单元 | 容量 | 参考 rank | 物理 bin |
|---|---:|---:|---:|---:|
| `pool_01` | 100 | 125 GiB | 50 | 20 |
| `pool_02` | 100 | 125 GiB | 50 | 20 |
| `pool_03` | 100 | 125 GiB | 50 | 20 |
| `background` | 2,100 | 2625 GiB | 50 | 20 |

四个 150 秒阶段依次以 pool_01、pool_02、pool_03、pool_01 为当前热点池。
每阶段只访问当前热点池 85.41% 和 background 14.59%，另外两个小池为 0%。
每个 pool 的 16/32/64/128/256 MiB 固定大小档内部先计算 50 个参考 rank 的
Zipf(0.99)：前10个单独保留，后40个每4个合并，形成20个物理bin。小池
头部/尾部bin分别为2.5/10 GiB，background分别为52.5/210 GiB。
每阶段200 FWD；第一和第四阶段复用一套FWD。全部为4 MiB Direct I/O、
`fwdrate=max`，总时长仍为600秒。

数据目录为 `$ANCHOR_ROOT/bigdata_mapreduce_vdbench_v1`；配置不包含 `hd=`。
