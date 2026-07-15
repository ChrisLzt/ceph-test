# SYSU WRF 生命周期 Vdbench 负载

这是单节点 WRF 生命周期模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/hpc_wrf_vdbench_v1/README.md`](../../new_workload/hpc_wrf_vdbench_v1/README.md)。

startup、checkpoint、history 各 800 单元、250 GiB、80 rank；每 rank 10
单元、3.125 GiB，包含 160/80/40/20/10 个 4/8/16/32/64 MiB 文件。

阶段为 `startup_read → checkpoint_read → history_read → checkpoint_reheat`。
四个阶段各 150 秒，热点在边界直接切换，最后 checkpoint 复热。每个活动组
的五个固定大小档独立计算 Zipf(0.99)，再聚合到 80 rank。全部为 4 MiB Direct I/O、
`fwdrate=max`，合计 600 秒。

数据目录为 `$ANCHOR_ROOT/hpc_wrf_vdbench_v1`；配置不包含 `hd=`。保留的 IOR
版本位于 [`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md)。
