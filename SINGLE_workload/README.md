# SINGLE 单节点五负载

这里只保留当前五种负载，每个用例目录包含README、生成/校验/准备/运行脚本及rendered配置。

| 目录 | 场景 | GiB | 阶段数 |
|---|---|---:|---:|
| [bigdata_baleen_v2](bigdata_baleen_v2/README.md) | Baleen原生trace统计 |188.2793|1|
| [graph_graphchi_psw_v2](graph_graphchi_psw_v2/README.md) | GraphChi PSW＋Zipf |128|4|
| [hpc_wrf_continuous_v2](hpc_wrf_continuous_v2/README.md) | WRF事件组＋Zipf |112|7|
| [ai_training_ses_v2](ai_training_ses_v2/README.md) | SES PERF_002设计＋Zipf |114.8907|1|
| [ai_inference_ses_v2](ai_inference_ses_v2/README.md) | SES PERF_003设计＋Zipf |115|1|

合计658.1700439453125GiB。每项600秒，纯读，fwdrate=max，无stopafter，每RD活跃FWD≤256。
默认profile=current，baseline为同布局对照，不是另一套负载。AI无需SES运行环境。

```bash
# 从仓库根执行；以下均不启动压测
SINGLE_workload/single_current.sh
SINGLE_workload/render_all.sh
SINGLE_workload/validate_all.sh
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --dry-run
```

[使用说明](USAGE.md)列出数据目录、准备/运行命令及原版Vdbench兼容规则。
真实造数或压测需用户授权和--execute。目录整理不修改CephFS数据，也不表示数据已READY。
SYSU、INSPUR和no_migration_workload不在本次清理范围。
Heat Predictor工具、实验结果及参考材料位于`/home/chris/ceph-tool`。
