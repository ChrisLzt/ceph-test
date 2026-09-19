# 基于SES 1.2.0的AI训练

依据PERF_002模板设计：小文件/大文件承担60%/40%的请求，保留不同文件大小类别及访问构成，源写转换为读，类别内加入Zipf(0.99)。单RD600秒。SES仅为设计来源，不导入SES框架、不使用ResearchCase或SES报告，不执行真实神经网络训练。

容量：114.8907470703125 GiB；物理文件：10000；最大活跃FWD：255。
数据目录：`/mnt/cephfs/single_ses_perf_zipf_v1/ai_training_ses_v2`。

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
