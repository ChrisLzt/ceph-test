# SES 1.2.0 AI 推理（SINGLE v2）

PERF_003 模板适配。512 MiB/1 GiB/2 GiB 文件各 30/40/30 个；纯读、60% 顺序/40% 随机、64/128 KiB 各半。没有显式 KV cache 生命周期。类别内 Zipf 分组近似 TV 约 13.77%，不是严格全局 Zipf。

当前精确容量 **115.0 GiB**，100 个数据文件；单 RD 最多 96 个测量 FWD，准备每批最多 20 个 FWD。默认数据根目录 `/mnt/cephfs/single_v2/ai_inference_ses_v2`。

## 使用与边界

- `render_config.sh` 仅生成配置/manifest，绝不创建数据目录。`DATA_ROOT` 是五用例共同父目录；`CONFIG_ROOT` 是五用例配置父目录；`FWDRATE` 默认 100（未校准的平均目标 IOPS），也可显式选择 max 饱和模式。
- `validate_model.sh` 校验全部已渲染配置与 manifest；prepare 和各 profile 独立文件，默认/对照共用同一个布局。
- `prepare_data.sh --execute --results /绝对路径/新结果根目录` 才会写入数据，运行前需得到用户造数授权。脚本不自动渲染，使用经过核对的配置。当前服务器空间不足，见 suite README。
- `run_test.sh --execute --results /绝对路径/新结果根目录` 才会测量；测量默认 baseline，需另行获得压测授权。测量前校验 ready 标记和完整文件身份、大小、分配空间。
- 准备要求专用目录为空、真实 CephFS 挂载和足够空间，不自动 clean、删除、重挂载或修复。失败保留现场；本版没有自动续作入口，不手动伪造 ready 标记。

`rendered/model.json` 保存模型语义和来源，`manifest.json` 保存数据布局与配置哈希。每个 bin 固定 `depth=1,width=1`，数据文件路径是 `bin/vdb.1_1.dir/vdb_f0000.file` 起，索引与固定成员顺序对应；不要重新随机映射对象。

原始读写比例仅作来源元数据；所有正式测量 FWD 为 read，format=no。准备本身必须真实写入文件，不是稀疏占位，也不是纯读。

## SES 环境

运行入口使用 `SES_PYTHON` / `PYTHON_BIN` 指定的 Python，默认指向同级 ceph-tool 的 `.venv-ses120/bin/python`。必须设置 `SES_SOURCE_ROOT` 为已冻结的 SES 1.2.0 包目录。独立环境和来源资料留在 ceph-tool，不属于正式仓库。

执行适配器使用真实 SES Suite/BaseCase/CaseRunner/Report 生命周期，覆盖原版隐式准备/清理、最小容量校验和报告打包。报告标为研究适配结果，不作为 SES 标准认证成绩；没有执行训练计算、模型推理或真实 KV tensor 生成。

离线解析已使用固定 Vdbench 5.04.07 jar 的 `-s` 模式通过；实测覆盖率、吞吐与对象热度仍需后续运行验证。更多命令和限制见 [SINGLE 总览](../README.md)。
