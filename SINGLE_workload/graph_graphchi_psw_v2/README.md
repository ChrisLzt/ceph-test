# GraphChi 图计算

依据GraphChi PSW访问结构和web-Google拓扑划分四个顶点区间。每阶段访问对应源行与目标列的并集，对角片段只计一次；cell内加入Zipf(0.99)。四阶段各150秒。区间数、容量、时长为工程参数，不执行完整GraphChi计算或要求完整扫描。

容量：128.0 GiB；物理文件：2048；最大活跃FWD：116。
数据目录：`/mnt/cephfs/single_business_phase_v1/graph_graphchi_psw_v2`。

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
