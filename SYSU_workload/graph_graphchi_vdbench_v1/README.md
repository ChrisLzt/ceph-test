# SYSU GraphChi shard内Zipf冷热负载

这是单节点GraphChi shard生命周期模型的750 GiB物理版本。来源和适用边界见
[`../../new_workload/graph_graphchi_vdbench_v1/README.md`](../../new_workload/graph_graphchi_vdbench_v1/README.md)。

- 4个等容量shard，每个600单元、187.5 GiB；
- 每shard 100 rank，每rank 6单元、1.875 GiB；
- 每rank包含96/48/24/12/6个4/8/16/32/64 MiB文件；
- 总计400 rank、2,400单元、750 GiB。

四阶段依次处理shard 00–03，每阶段150秒，只访问当前shard，并在五个固定
大小档内分别计算Zipf(0.99)。热点在阶段边界直接切换，每阶段500 FWD。全部
为4 MiB顺序读、Direct I/O、`fwdrate=max`，合计600秒。

当前版本不实现PSW window。旧`window_src*`目录会在下一次prepare时清理。
数据目录为`$ANCHOR_ROOT/graph_graphchi_vdbench_v1`；配置不包含`hd=`。
