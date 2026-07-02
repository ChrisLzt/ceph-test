# MapReduce vdbench 文件冷热负载 v1

## 1. 用途

本负载用于验证存储系统能否根据文件访问热度识别小容量热点、跟踪热点迁移，并将长期未访问的数据保持在冷层。

这是一个**来源驱动的新负载**，不继承旧随机文件测试中的 400 KiB 文件、90/10 读写比或 128 KiB 请求。首版只实现公开论文能够直接支持、且适合做冷热识别的三个特征：

1. 年轻文件只占很小容量，但贡献大多数访问。
2. 大量文件在观察期内完全未访问，构成 inactive storage。
3. 文件总体是动态 population，因此增加热点轮换和复热阶段。

短生命周期、create/delete burst 和自相似到达在论文中也有证据，但 v1 暂不实现；参见 [SOURCES.md](SOURCES.md) 的覆盖矩阵。

## 2. 权威来源

主要来源是 Cristina L. Abad 等人在 IEEE IISWC 2012 发表的论文：

> A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal Locality and Arrival Patterns

论文分析 Yahoo! 两个多 PB Hadoop 集群的 6 个月 namespace trace，覆盖超过 9.4 亿次 create 和 120 亿次 open。论文和参数映射详见 [SOURCES.md](SOURCES.md)。

- DOI：<https://doi.org/10.1109/IISWC.2012.6402909>
- 作者公开全文：<https://assured-cloud-computing.illinois.edu/files/2014/03/A-Storage-Centric-Analysis-of-MapReduce-Workloads-File-Popularity-Temporal-Locality-and-Arrival-Patterns.pdf>
- Vdbench 官方下载及 5.04.06 User Guide：<https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

## 3. 模型

### 3.1 Namespace 和容量

| 对象池 | 文件数 | 单文件大小 | 容量 | 用途 |
|---|---:|---:|---:|---|
| pool_01 | 200 | 12 MiB | 2,400 MiB | 候选热点 A |
| pool_02 | 200 | 12 MiB | 2,400 MiB | 候选热点 B |
| pool_03 | 200 | 12 MiB | 2,400 MiB | 候选热点 C |
| pool_04 | 5,000 | 12 MiB | 60,000 MiB | 活跃背景数据 |
| pool_05 | 4,400 | 12 MiB | 52,800 MiB | 全程不访问的冷数据 |
| 合计 | 10,000 | — | 120,000 MiB（约 117.19 GiB） | — |

映射结果：

- 当前热点池占 2% 容量，接近论文 PROD 中“年龄不超过 1 天的文件只占 2.21% bytes”的观测。
- 当前热点获得 85% 操作，接近论文 PROD 中“年龄不超过 1 天的文件贡献 85.41% accesses”的观测。论文同时给出 R&D：1 天内文件贡献 78.91% accesses、占 1.87% bytes；v1 默认使用 PROD，不混用 R&D 参数。
- inactive 容量占 44.00%，落在论文的 42%～46% bytes 区间。
- 因为 5 个 FSD 单文件大小统一为 12 MiB，文件数比例等于容量比例，所以当前热点文件数也为 2%，低于论文 PROD 的 3.67% files；inactive 文件占比也变为 44.00%，不再保留论文的 inactive 文件数 51%～52% 观测值。v1 当前选择“容量占比优先”。

单个文件的 12 MiB 大小不是论文观测值。论文明确说明 trace 缺少 I/O 信息，无法知道 open 读取了多少字节；该大小只是为了在当前单节点 CephFS 测试预算中得到约 117.19 GiB，并让文件数比例等于容量比例。不能把 12 MiB 宣称为 Yahoo! 生产文件大小。

### 3.2 阶段

| 阶段 | A | B | C | 背景 | inactive | 目的 |
|---|---:|---:|---:|---:|---:|---|
| hot_a | 85% | 1% | 1% | 13% | 0% | A 成为“1 天内年轻文件”热点 |
| hot_b | 1% | 85% | 1% | 13% | 0% | 年轻热点 A→B |
| hot_c | 1% | 1% | 85% | 13% | 0% | 年轻热点 B→C |
| reheat_a | 85% | 1% | 1% | 13% | 0% | 冷却后的 A 再升温 |

热点阶段中，85% 来自论文 PROD 的 1 天内文件 access share；1/1/13 是把剩余 15% 按非热点活跃文件数取整分配，并非论文独立给出的比例。

热点每阶段轮换一次是用于评价识别速度的工程扩展。论文证明 population 高度动态，但没有给出“每 N 分钟轮换热点池”的参数，所以阶段时长必须根据被测系统识别周期设置，而不能作为 Yahoo! trace 的原始时间尺度。

对象池名称不包含 hot/cold 语义，避免被测系统从路径名称而不是访问行为推断分类。冷热真值不再由本目录提供，测试时由使用者根据阶段和被测系统观测自行判断。

## 4. data profile

[configs/prepare_data.vdb.in](configs/prepare_data.vdb.in) 只负责创建测试数据集，[configs/run_test.vdb.in](configs/run_test.vdb.in) 只负责正式冷热阶段。正式阶段对对象池做 1 MiB 顺序读取，用于让 CephFS/OSD 数据路径产生可观测热度。论文给出了按访问次数统计的 temporal-locality 容量关系，但没有记录实际读取字节数或请求大小，因此：

- 1 MiB transfer size 是工程参数，不是论文结论。
- data proxy 结果不能标为论文原始 I/O 分布。
- 更改 transfer size 会改变字节热度和性能结果。

## 5. 生成配置

```bash
cd /home/chris/ceph-test/new_workload/bigdata_mapreduce_vdbench_v1
./render_config.sh
```

默认会生成两个独立配置：

- `rendered/prepare_data.vdb`：只包含 `prepare_clean` 和 `prepare_create`，用于造数据。
- `rendered/run_test.vdb`：只包含 `hot_a/hot_b/hot_c/reheat_a`，用于正式测试；该文件不包含任何 `format=`。

也可以只渲染其中一个：

```bash
./render_config.sh prepare
./render_config.sh run
```

可通过环境变量覆盖：

```bash
ANCHOR=/mnt/cephfs/bigdata_mapreduce_vdbench_v1 \
VDBENCH_HOME=/home/chris/PDSL/vdbench \
REMOTE_USER=chris \
HOST1=s52.servers.hustpdsl.cn \
PHASE_SECONDS=150 \
FWD_RATE=1000 \
./render_config.sh
```

默认数据路径为 `/mnt/cephfs/bigdata_mapreduce_vdbench_v1`，不再添加 `new_workload/` 中间层。默认 Vdbench 目录为 `/home/chris/PDSL/vdbench`，默认只使用当前单节点 `s52.servers.hustpdsl.cn`。如后续改为多客户端，需要重新扩展模板中的 `hd=` 定义，并确保所有客户端都能访问相同 `ANCHOR` 路径。

渲染结果写入 `rendered/`，模板本身不会被修改。旧的合并配置 `rendered/data_heat_proxy.vdb` 不再生成，避免正式测试时误执行 prepare。

## 6. 执行

运行前先检查参数和容量：

```bash
./validate_model.sh
```

第一次造数据：

```bash
./prepare_data.sh
```

`prepare_data.sh` 会渲染并执行 `rendered/prepare_data.vdb`。其中 `prepare_clean` 通过 `format=(clean,only)` 清理旧结构，`prepare_create` 通过 `format=(restart,only)` 创建约 117.19 GiB 文件。这个脚本会清理/重建数据，只应在需要重新造数时运行。

后续正式测试：

```bash
./run_test.sh
```

`run_test.sh` 会渲染并执行 `rendered/run_test.vdb`。该配置没有 `format=`，不会执行 clean/create，不会重新造数据。默认正式测试包含 4 个阶段，每阶段 `PHASE_SECONDS=150`，总时长约 10 分钟。

### Java 兼容性

当前目录中的版本已更新为 Vdbench 5.04.07，并已在本机 OpenJDK 11.0.31 上通过启动检查。所有客户端仍须使用一致的 Vdbench/Java 组合。

### 已完成的本地验证

- Vdbench 5.04.07 `-s` 已完整解析 `prepare_data.vdb` 和 `run_test.vdb`。

尚未完成当前 CephFS 约 117.19 GiB 数据集的完整正式运行，因此当前结论只是“配置可解析且模型可生成”。

## 7. 运行前必须确定的参数

当前为了统一五类负载的对比窗口，默认正式测试总时长固定为 10 分钟，即 4 个阶段各 150 秒。如果后续要根据被测系统内部周期重新设定，应取得：

1. 被测系统热度统计窗口。
2. promotion/demotion 判断周期。
3. 数据迁移周期。

每个阶段应足够长，使系统至少完成若干次识别判断；具体倍数作为测试设计参数记录。若无法取得内部周期，先使用当前 10 分钟统一窗口，再做多个阶段时长的 sensitivity test。

`FWD_RATE` 也不能直接设为 `max`。先在单独环境测最大 metadata/data rate，再选择不会长期排队的固定速率；Vdbench 使用 `abort_failed_skew=2` 检查实际 skew 偏差。

## 8. 验收

负载符合度：

- Vdbench `skew.html` 中各 FWD 的实际 share 与目标相差不超过 2 个百分点。
- 阶段切换时总 `fwdrate` 保持不变。
- inactive 池在正式阶段操作数为 0。
- 每阶段无 I/O 或数据校验错误。

冷热识别：

- `hot_a/hot_b/hot_c/reheat_a` 的目标热点分别是 A/B/C/A。
- 记录 time-to-promote、time-to-demote、time-to-reheat。
- 同时记录按文件数和按字节数计算的 precision/recall/F1。
- 记录快速层迁移字节、后台带宽以及各池 P95/P99 时延。

## 9. v1 已知边界

- 论文来自 2011 年 Yahoo! Hadoop 集群，只代表该类 MapReduce workload。
- v1 没有执行 Hadoop/MapReduce，也不模拟 HDFS replication、block placement 或 NameNode RPC。
- v1 只实现 temporal locality 和 inactive capacity，不实现论文中的完整 power-law tail。
- v1 没有实现 AOA/AOD percentile、create/delete 生命周期和 Hurst/self-similar arrivals。
- 论文中 1 天内文件的 2.21% bytes/85.41% accesses 是 6 个月聚合结果；把它放入每个测试阶段是用于可测识别的缩放模型。
- 如果获得目标系统审计 trace，应优先重新拟合，而不是继续使用该公开参考参数。
