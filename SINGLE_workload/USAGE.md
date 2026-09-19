# 当前 SINGLE 五负载套件

统一配置根：`/home/chris/ceph-test/SINGLE_workload`。统一运行 profile：`current`。
`current` 是已确认方案的明确选择，不代表五项都使用相同分布。

| 用例 | 来源方案 | GiB | 物理文件 | RD数 | 最大活跃FWD |
|---|---|---:|---:|---:|---:|
| Baleen | 全样本原生频率、单RD、不加Zipf | 188.279296875 | 29819 | 1 | 255 |
| GraphChi | PSW四区间、cell内Zipf | 128 | 2048 | 4 | 116 |
| WRF | 七事件组、角色内Zipf | 112 | 1792 | 7 | 40 |
| SES训练 | PERF_002纯读、大小类别内Zipf | 114.8907470703125 | 10000 | 1 | 255 |
| SES推理 | PERF_003、100逻辑文件各拆2分片、逻辑文件Zipf | 115 | 200 | 1 | 200 |

合计658.1700439453125GiB、43,859物理文件。各用例600秒RD预算，启动/切换另计；全部纯读、max、无stopafter。current保留来源模型的所有访问配额，不重新调整热度。

## 默认数据路径

| 用例 | 数据目录 |
|---|---|
| Baleen | `/mnt/cephfs/single_baleen_static_v1/bigdata_baleen_v2` |
| GraphChi | `/mnt/cephfs/single_business_phase_v1/graph_graphchi_psw_v2` |
| WRF | `/mnt/cephfs/single_structural_zipf_v2/hpc_wrf_continuous_v2` |
| SES训练 | `/mnt/cephfs/single_ses_perf_zipf_v1/ai_training_ses_v2` |
| SES推理 | `/mnt/cephfs/single_structural_zipf_v2/ai_inference_ses_v2` |

只是统一配置入口，不搬动数据。每项manifest保存独立数据路径、布局hash和配置hash；provenance.current_suite记录来源设计/profile。符合相同布局且经verify通过的数据可以复用；存在目录并不表示已经READY。Baleen静态、WRF重分组和推理分片相对于各自旧方案仍需匹配新布局。

## 离线入口

在 `/home/chris/ceph-test` 执行：

```bash
SINGLE_workload/single_current.sh                 # 默认preview，仅校验配置并列出计划
SINGLE_workload/render_all.sh                    # 重新生成当前五项配置
SINGLE_workload/validate_all.sh                  # 配置、模型测试、shell语法检查
SINGLE_workload/single_current.sh preview --case ai_inference
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --dry-run
```

render不创建数据目录。`CONFIG_ROOT`可以覆盖配置根；显式`DATA_ROOT`可以为重新渲染指定共同数据父目录，否则保持表中各自路径。当前生成器只接受max。

`SINGLE_workload/<v2用例>/render_config.sh`、`validate_model.sh`、`prepare_data.sh`、`run_test.sh`也默认指向本配置根，run默认profile=current。同目录保留baseline作为同数据布局的对照配置。

统一入口的 `--case` 接受 baleen、graphchi、wrf、ai_training、ai_inference 或 all。低层 `python -m workload_common.single_v2` 同样默认current设计、current profile和max；历史设计只能显式生成到其他配置根。

## 造数与运行交接（本轮没有执行）

只读准备检查：

```bash
SINGLE_workload/single_current.sh preflight --case baleen
SINGLE_workload/single_current.sh verify --case graphchi
```

preflight检查空间与待准备目录；verify检查READY和实际库存。已有数据不应盲目prepare；造数前空间需重查，不自动清理旧目录。

获得用户真实执行授权后才可使用：

```bash
SINGLE_workload/single_current.sh prepare --case baleen --execute \
  --results /home/chris/ceph-tool/results/prepare-全新批次

export VDBENCH_HOME=/home/chris/PDSL/vdbench
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --execute --collect-trace \
  --output-root /home/chris/ceph-tool/results/hp_runs/全新批次
```

矩阵默认current；执行前检查全部所选布局READY与HP部署，再重置/测量。没有--execute时矩阵默认dry-run。统一包装脚本的prepare/run没有--execute会在访问数据之前拒绝。run默认使用python3和原版Vdbench 5.04.07；`PYTHON_BIN`和`VDBENCH_HOME`可显式覆盖，覆盖者需保证依赖与runtime兼容。

裸Vdbench测量也可用single_current.sh run，但它不负责HP重置、采样、trace或指标汇总；正式冷热识别请用矩阵入口。prepare_data.sh/run_test.sh不能在没有用户授权时启动。

## 对照和来源

本根的baseline：Baleen仍为原生频率（与current相同），其他四项为同结构同布局的组内均匀访问。
五个用例的README说明来源与适配；完整参数及来源证据记录在各自rendered/model.json中。
旧v1、IOR、早期v2及file_zipf/business_phase/baleen_static配置目录已移除。
历史代码可从Git历史查看；原生频率/Zipf设计概率不等于实测对象热度，不保证识别指标。

## 原版 Vdbench 兼容（2026-09-19）

默认使用未修改的 Vdbench 5.04.07，不再依赖 fractional-xfer 补丁。混合
`xfersize` 的各大小请求百分比先四舍五入，再按最大欠配/超配修正整数余数，
确保总和恰好100；舍去0%类别。相同误差按原类别顺序处理，结果可复现。
只量化传输大小配比，FWD skew仍保留小数，文件访问权重、文件布局、容量、
600秒阶段、max及FWD数量不变。model.json保留源概率，VDB配置为整数近似。
低频传输大小可能消失，字节流量及对象热度可能变化；不能声称完整保留trace请求大小分布。
已有数据是否可用仍由布局hash及verify决定。

AI仅以SES 1.2.0的PERF_002/PERF_003为设计来源，保留模板参数和来源哈希。
五项统一直接执行原版Vdbench，不导入SES框架、不使用ResearchCase、不生成SES报告。
无需安装SES或设置SES_SOURCE_ROOT、SES_PYTHON，普通python3即可运行负载脚本。
Vdbench统计保留在结果目录，冷热识别指标由Heat Predictor工具采集与分析。
未执行真实神经网络训练或推理，不作为SES认证测试。

本次量化审计：按FWD权重平均的请求大小分布TV，Baleen约6.2088%、
训练0.4%、其他三项0；Baleen最差单FWD约61.7966%，低频大小类别损失明显。
平均请求大小变化分别为Baleen +0.1203%、训练 -0.0372%、其余0。
这些是配置概率的变化，不是实测值，也不代表文件选择概率发生同等变化。
