# WRF 高性能计算

依据WRF input/boundary/history/restart角色组织七个事件组：cold_start 80秒；history_01_04 100秒；history_05_08 100秒；restart_08h_output 60秒；history_09_12 100秒；history_13_16 100秒；restart_16h_output 60秒。每个角色内Zipf(0.99)，角色配额为工程适配。源输出操作映射为对预创建文件的读取，不模拟故障恢复，不执行WRF计算。

容量：112.0 GiB；物理文件：1792；最大活跃FWD：40。
数据目录：`/mnt/cephfs/single_structural_zipf_v2/hpc_wrf_continuous_v2`。

## 配置与使用

- `rendered/run_current.vdb`：当前正式配置，默认profile=current。
- `rendered/run_baseline.vdb`：相同数据布局的对照配置。
- `rendered/prepare_data.vdb`：独立造数据配置。
- `rendered/model.json`：模型、阶段、来源与适配证据。
- `rendered/manifest.json`：文件布局、数据路径和配置哈希。

本目录的render_config.sh、validate_model.sh、prepare_data.sh、run_test.sh分别用于
生成、校验、造数和测量。默认普通python3与原版Vdbench5.04.07；支持PYTHON_BIN和VDBENCH_HOME覆盖。
CONFIG_ROOT默认为SINGLE_workload，render不创建数据。所有正式测量纯读、fwdrate=max、无stopafter。
真实造数/压测仍需用户授权与--execute；保留READY、实际库存、CephFS及输出路径检查。

来源固定数据位于`../../workload_common/single_v2/data/`。详细命令、整数xfersize误差及实验边界见
[套件使用说明](../USAGE.md)。
