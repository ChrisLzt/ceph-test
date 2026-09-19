# WRF 高性能计算（SINGLE v2）

默认连续预报：输入/边界、16 个 history 帧、两个 restart 输出；19 个事件共 600 秒。写直接转读，不要求故障恢复，不回读 restart，不提供 Zipf profile。

当前精确容量 **112.0 GiB**，1792 个数据文件；单 RD 最多 2 个测量 FWD，准备每批最多 20 个 FWD。默认数据根目录 `/mnt/cephfs/single_v2/hpc_wrf_continuous_v2`。

## 使用与边界

- `render_config.sh` 仅生成配置/manifest，绝不创建数据目录。`DATA_ROOT` 是五用例共同父目录；`CONFIG_ROOT` 是五用例配置父目录；`FWDRATE` 默认 100（未校准的平均目标 IOPS），也可显式选择 max 饱和模式。
- `validate_model.sh` 校验全部已渲染配置与 manifest；prepare 和各 profile 独立文件，默认/对照共用同一个布局。
- `prepare_data.sh --execute --results /绝对路径/新结果根目录` 才会写入数据，运行前需得到用户造数授权。脚本不自动渲染，使用经过核对的配置。当前服务器空间不足，见 suite README。
- `run_test.sh --execute --results /绝对路径/新结果根目录` 才会测量；测量默认 baseline，需另行获得压测授权。测量前校验 ready 标记和完整文件身份、大小、分配空间。
- 准备要求专用目录为空、真实 CephFS 挂载和足够空间，不自动 clean、删除、重挂载或修复。失败保留现场；本版没有自动续作入口，不手动伪造 ready 标记。

`rendered/model.json` 保存模型语义和来源，`manifest.json` 保存数据布局与配置哈希。每个 bin 固定 `depth=1,width=1`，数据文件路径是 `bin/vdb.1_1.dir/vdb_f0000.file` 起，索引与固定成员顺序对应；不要重新随机映射对象。

原始读写比例仅作来源元数据；所有正式测量 FWD 为 read，format=no。准备本身必须真实写入文件，不是稀疏占位，也不是纯读。

离线解析已使用固定 Vdbench 5.04.07 jar 的 `-s` 模式通过；实测覆盖率、吞吐与对象热度仍需后续运行验证。更多命令和限制见 [SINGLE 总览](../README.md)。
