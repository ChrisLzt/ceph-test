# Baleen 大数据

基于Baleen Region4冻结trace样本的29819个键，将完整样本GET/PUT次数汇总为原生访问频率，所有请求转换为读。255个桶近似文件频率，单RD600秒；不是逐请求或原时间轴回放，不额外叠加Zipf。请求大小配比按原版Vdbench要求整数化。

容量：188.279296875 GiB；物理文件：29819；最大活跃FWD：255。
数据目录：`/mnt/cephfs/single_baleen_static_v1/bigdata_baleen_v2`。

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
