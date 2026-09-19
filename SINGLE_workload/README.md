# SINGLE 当前五负载

默认脚本已统一到 [current套件](current/README.md)，运行profile为`current`：

| 用例 | 当前方案 | GiB | 阶段数 |
|---|---|---:|---:|
| 大数据 Baleen | 完整trace原生统计、单RD，无Zipf | 188.2793 | 1 |
| 图计算 GraphChi | PSW区间＋cell内Zipf | 128 | 4 |
| HPC WRF | 七事件组＋角色内Zipf | 112 | 7 |
| AI训练 | SES1.2.0 PERF_002纯读＋类别内Zipf | 114.8907 | 1 |
| AI推理 | SES1.2.0 PERF_003逻辑文件双分片＋Zipf | 115 | 1 |

总计658.1700439453125GiB；每项600秒、纯读、fwdrate=max、不设置stopafter、每RD活跃FWD≤256。SYSU和INSPUR不在本次调整范围。

```bash
# 从 /home/chris/ceph-test 执行，以下均不启动压测
SINGLE_workload/single_current.sh
SINGLE_workload/render_all.sh
SINGLE_workload/validate_all.sh
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --dry-run
```

[single_current.sh](single_current.sh)提供统一preview/render/validate/preflight/verify/parser-check/prepare/run入口。默认preview；prepare/run要求--execute，真实操作仍须用户授权。五个v2目录中的包装脚本也默认使用current根。各用例实际数据目录、SES环境及复用要求见[current说明](current/README.md)。

统一入口保留各模型已有数据路径，不自动创建、搬迁或删除Ceph数据。不同布局的旧READY不能复用。不要因脚本已完成就认定数据已准备或可以直接压测。

## 保留的来源与历史入口

- 五个原v2目录中的rendered配置：早期来源适配基线；其包装脚本现默认current。
- [business_phase](business_phase/README.md)：各项结构化Zipf的专项配置，含旧Baleen四窗对照。
- [baleen_static](baleen_static/README.md)：新Baleen静态原生频率专项入口。
- [file_zipf](file_zipf/README.md)：此前全文件Zipf对照。
- 五个旧v1 prepare/run已停用；IOR不在当前五项集合。

HP实验编排、评估、参考资料和结果位于`/home/chris/ceph-tool`，不在负载仓库。本轮不commit或push。
