# SYSU WRF 生命周期 Vdbench 负载

这是单节点 WRF 生命周期模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/hpc_wrf_vdbench_v1/README.md`](../../new_workload/hpc_wrf_vdbench_v1/README.md)。

startup、checkpoint、history 各800单元、250 GiB。每组以100个参考rank计算
Zipf并压缩为40个物理bin：前20个各8单元、2.5 GiB，后20个各32单元、10 GiB。

阶段为
`startup_read → checkpoint_write → history_write → checkpoint_reheat`，
即 `R → W → W → R`。WRF 官方语义中，startup 状态是输入，restart/checkpoint
和 history/output 是运行期间写出的文件；checkpoint 随后可被读取用于恢复。
四个阶段各 150 秒，热点在边界直接切换，最后 checkpoint 复热。

每个活动组的五个固定大小档独立计算 Zipf(0.99)，再聚合到 40 个物理 bin。
checkpoint 写入和复热读取访问同一批 FSD，但使用权重相同、操作不同的两套
FWD；每阶段 200 FWD。写阶段覆盖 prepare 已创建的文件，不改变文件数和容量。
全部为 4 MiB Direct I/O、`fwdrate=max`，合计 600 秒。

WRF 文件语义来源：
<https://www2.mmm.ucar.edu/wrf/site/documentation/namelist.input_best_practices.html>。

数据目录为 `$ANCHOR_ROOT/hpc_wrf_vdbench_v1`；配置不包含 `hd=`。保留的 IOR
版本位于 [`../hpc_wrf_ior_v1`](../hpc_wrf_ior_v1/README.md)。
