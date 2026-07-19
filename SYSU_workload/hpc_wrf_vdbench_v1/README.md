# SYSU WRF 生命周期 Vdbench 负载

这是单节点 WRF 生命周期模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/hpc_wrf_vdbench_v1/README.md`](../../new_workload/hpc_wrf_vdbench_v1/README.md)。

startup、checkpoint、history 各800单元、250 GiB。每组以100个参考rank计算
Zipf并压缩为40个物理bin：前20个各8单元、2.5 GiB，后20个各32单元、10 GiB。

阶段为 `startup_read → checkpoint_read → history_read → checkpoint_reheat`。
四个阶段各 150 秒，热点在边界直接切换，最后 checkpoint 复热。每个活动组
的五个固定大小档独立计算Zipf(0.99)，再聚合到40个物理bin。第二和第四阶段
复用同一套checkpoint FWD，每阶段200 FWD。全部为4 MiB Direct I/O、
`fwdrate=max`，合计600秒。

数据目录为 `$ANCHOR_ROOT/hpc_wrf_vdbench_v1`；配置不包含 `hd=`。保留的 IOR
版本位于 [`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md)。
