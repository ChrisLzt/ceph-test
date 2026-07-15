# SYSU MapReduce 文件冷热负载

这是单节点 MapReduce 模型的 750 GiB 物理版本。来源、论文比例和适用范围见
[`../../new_workload/bigdata_mapreduce_vdbench_v1/README.md`](../../new_workload/bigdata_mapreduce_vdbench_v1/README.md)。

| 数据池 | 单元 | 容量 | rank | 每 rank 容量 |
|---|---:|---:|---:|---:|
| `pool_01` | 96 | 30 GiB | 24 | 1.25 GiB |
| `pool_02` | 96 | 30 GiB | 24 | 1.25 GiB |
| `pool_03` | 96 | 30 GiB | 24 | 1.25 GiB |
| `background` | 2,112 | 660 GiB | 24 | 27.5 GiB |

四个 150 秒阶段依次使用 `85/1/1/13%`、`1/85/1/13%`、`1/1/85/13%`、
`85/1/1/13%` pool 访问份额，边界直接切换，background 始终为 13%。每个 pool 的
4/8/16/32/64 MiB 固定大小档内部按 Zipf(0.99) 聚合到 24 个 rank。全部为
4 MiB Direct I/O、`fwdrate=max`，总时长仍为 600 秒。

数据目录为 `$ANCHOR_ROOT/bigdata_mapreduce_vdbench_v1`；配置不包含 `hd=`。
