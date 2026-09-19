# 基于SES 1.2.0的AI推理

依据PERF_003模板设计：源写转换为读后，顺序/随机读取占60%/40%，64/128KiB请求各半，类别内逻辑文件Zipf(0.99)。100个逻辑文件各拆为两个等容量分片，共200物理文件。单RD600秒。SES仅为设计来源，无SES框架/报告运行依赖，不执行真实模型推理。

容量：115.0 GiB；物理文件：200；最大活跃FWD：200。
数据目录：`/mnt/cephfs/single_structural_zipf_v2/ai_inference_ses_v2`。

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
