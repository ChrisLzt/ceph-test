# 当前 SINGLE 五负载套件

统一配置根：`/home/chris/ceph-test/SINGLE_workload/current`。统一运行 profile：`current`。
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

`SINGLE_workload/<v2用例>/render_config.sh`、`validate_model.sh`、`prepare_data.sh`、`run_test.sh`也默认指向本current配置根，run默认profile=current。需要旧方案时必须同时明确CONFIG_ROOT和--profile，不能靠默认值选择旧版。

统一入口的 `--case` 接受 baleen、graphchi、wrf、ai_training、ai_inference 或 all。低层 `python -m workload_common.single_v2` 为兼容历史仍保留原默认值，日常使用本包装脚本。

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

export SES_SOURCE_ROOT=/home/chris/ceph-tool/reference/资料/AI推理模型带宽测试_测试用例附件/002_storage_evaluation_system-src-v1.2.0/002_storage_evaluation_system-src-v1.2.0/storage_evaluation_system
export VDBENCH_HOME=/home/chris/ceph-tool/runtime/vdbench-fractional-xfer-v1
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --execute --collect-trace \
  --output-root /home/chris/ceph-tool/results/hp_runs/全新批次
```

矩阵默认current；执行前检查全部所选布局READY、SES依赖与HP部署，再重置/测量。没有--execute时矩阵默认dry-run。统一包装脚本的prepare/run没有--execute会在访问数据之前拒绝。run默认使用独立SES Python和小数xfersize runtime；`PYTHON_BIN`/`SES_PYTHON`和`VDBENCH_HOME`可显式覆盖，覆盖者需保证依赖与runtime兼容。

裸Vdbench测量也可用single_current.sh run，但它不负责HP重置、采样、trace或指标汇总；正式冷热识别请用矩阵入口。prepare_data.sh/run_test.sh不能在没有用户授权时启动。

## 对照和来源

本根的baseline：Baleen仍为原生频率（与current相同），其他四项为同结构同布局的组内均匀访问。旧source、file_zipf、business_phase与baleen_static目录保留为历史/专项入口，不会被render_all默认重写。

来源、业务适配及概率语义见 [静态Baleen](../baleen_static/README.md) 与 [结构化Zipf](../business_phase/README.md)。原生频率/Zipf设计概率不等于实测对象热度，不保证识别指标。本轮仅离线验证，无造数、压测或Git提交。
