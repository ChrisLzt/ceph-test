# 业务阶段 + 文件冷热差异（当前配置，2026-09-17）

Baleen 最新默认已改为 ../baleen_static 的单 RD 原生频率；本目录保留其四窗对照。其他四项及本目录对照的方案为 `phase_zipf099`：业务阶段决定活跃文件和必要的组间请求比例，组内按固定排名施加 Zipf(0.99)。阶段内均匀文件选择的对照叫 `baseline`，共享这套新布局；它不是原生基线。原生基线仍在上一层五个原目录，全程整体文件 Zipf 保留在 `../file_zipf/` 作为对照。

## 共同语义

- 单项总时长 600 秒，全部 RD 使用 `fwdrate=max`，每个 FWD 单线程、纯读。不设置 stopafter，文件访问持续行为使用 Vdbench 默认规则；不再强制每次选中文件仅执行一次 I/O。顺序访问保留 Vdbench 的文件内部偏移推进方式。
- 各阶段先分配业务组请求质量，再在组内按文件 rank 的 `r^-0.99` 归一化。它是**条件 Zipf**，不要求整个 600 秒的合计文件访问分布满足一条全局 Zipf，也不设置额外热池。
- 排名固定种子 `business-phase-zipf-v1`：对原 bin 与文件序号做 SHA-256 排序，组内排名固定，不按预测器结果挑种子。阶段切换只改变活跃集合/业务配额；同一组再次出现仍使用原排名。
- bin 内均匀选文件，按理论 Zipf 概率总质量选择 bin；使用 L1 分裂增益分配 bin 预算。`model.json` 的 `source_members` 映射 `[原 bin, 原文件零起始序号, 业务组内 rank]`，通常列表顺序为新文件序号；推理分片模型的 source_members 只列逻辑文件一次，fragments 另列两个物理文件的序号、逻辑偏移和长度。
- 每阶段最多 256 个**活跃 FWD**。不同 RD 的 FWD 定义数可以累加超过 256，不代表同时活跃。Baleen 有 512 个物理 bin；GraphChi、WRF、训练各 255 个，推理 100 个。物理 bin 数影响目录初始化，因此不声称启动速度一定比上一版快。准备时每 RD 20 个 FWD。
- 按用户确认将五项容量收敛至 112–128 GiB：Baleen 从原样本中分层抽取 20,307 文件至 128 GiB，其余四项库存保留；2026-09-16 两项 AI 分桶已重新生成。合计 34,347 个物理文件、597.8907470703125 GiB。推理文件拆成两个等容量分片，总容量不变，不截短 I/O 请求。
- 其他用例理论 TV 护栏为 6%；推理在逻辑文件级消除分桶平均误差（模型 TV=0，浮点容差1e-12），配置百分比序列化仍有微小取整误差。物理分片每对等热，不声称200个物理文件服从一条Zipf。TV不是分类准确率或实测分布误差。

| 用例 | GiB | 阶段数 | 物理 bin | 最大活跃 FWD | 最大阶段 TV |
|---|---:|---:|---:|---:|---:|
| Baleen | 128 | 4 | 512 | 256 | 4.871% |
| GraphChi | 128 | 4 | 255 | 116 | 2.172% |
| WRF | 112 | 7 | 255 | 40 | 1.172% |
| SES 训练 | 114.8907470703125 | 1 | 255 | 255 | 0.577% |
| SES 推理 | 115 | 1 | 100 | 200 | 逻辑文件模型 0% |

## 容量收敛：Baleen 固定分层抽样

仅修改 Baleen。按原 640 个 bin 分层，每层至少保留一个文件，固定种子 `baleen-capacity-128-v1` 选择文件；不改变被选中文件的大小或请求大小。20,307/29,819 文件被保留，容量从 188.279 GiB 降至精确 128 GiB。每个原始 bin 和窗口活跃模式都有代表，`capacity_adaptation` 和 `source_members` 保存完整选择口径及原文件索引。

这不是完整 trace 的所有 key。业务组权重和请求大小直方图仍来自完整原样本，是对抽样数据的统计驱动；不能声称被省略的 key 也被回放。原生 Baleen 基线保持原容量和完整库存，不受本次修改影响。Baleen 收敛时另外四项布局未变；随后两项 AI 已按上述新方案重新分桶。后续图表需使用本目录最新配置，不能混用旧容量截图。

## 1. Baleen：四个统计窗口

0–150、150–300、300–450、450–600 秒分别对应原始四个窗口，只访问该窗口原本活跃的文件。按文件大小及四窗口活跃掩码形成兼容组，保留该窗口各组原有 GET+PUT 操作占比，GET/PUT 都执行读；组内文件 Zipf。

保持随机文件内部访问。每个窗口的请求大小直方图在兼容组内按原始操作权重合并。因此保留组/窗口条件下的大小分布，但不保留原 key 或原 bin 与请求大小的精细相关性。不能称为逐请求 trace replay。

不同窗口活跃集合自然变化，同一组回归时排名不变。因为 `max` 已获用户指定，原 trace 窗口间的数值速率倍率不再控制实际 IOPS。

## 2. GraphChi：四个 PSW 窗口

四阶段各 150 秒，对应 interval 0、1、2、3。阶段 i 的活跃 cell 满足 `source_interval == i 或 destination_interval == i`，交集只计一次。保留 cell 的原请求配额，在每个活跃 cell 内使用文件 Zipf，4 MiB 顺序读。

含当前 memory shard 与其他 shard 的 sliding window 文件。活跃集合随 PSW 顺序切换，但偏斜抽样不保证读完每个 shard，也不再严格完成 PSW 全扫描。这是 PSW 结构下的冷热研究扩展，不执行 GraphChi 计算。原写回也以读取相同结构表示。

## 3. WRF：连续预报的 7 个分组 I/O 阶段

| 时间（秒） | 事件 | 活跃数据 |
|---|---|---|
| 0–80 | 启动输入 | input + boundary_0 |
| 80–180 | 第一组 history | history_01–04 |
| 180–280 | 第二组 history | history_05–08 + boundary_1 |
| 280–340 | 第一次 restart 输出适配 | restart_08h |
| 340–440 | 第三组 history | history_09–12 + boundary_2 |
| 440–540 | 第四组 history | history_13–16 + boundary_3 |
| 540–600 | 第二次 restart 输出适配 | restart_16h |

2026-09-17 落实新版七阶段分组：1,792 文件、112 GiB 保留，但重新分桶为255个bin，最大活跃FWD为40，最大理论TV约1.172%。同阶段四份history共用一个Zipf组，boundary单独成组；启动input/boundary配额80%/20%，含boundary的history阶段配额8/9、1/9，其他阶段100%分配给当前角色。配额按合成角色容量推导，不是WRF官方实测比例。

各组内部文件Zipf，4 MiB顺序读、纯读、max、无stopafter。不增加全量扫描，不保证文件覆盖。

同组四份 history 在一个 RD 内并发，boundary 与对应 history 组并发并持续更久；这是 WRF 事件分组适配，不保留逐个 history 输出的精细时序。history 与 restart 的源写操作全部转换为读取预建文件。

不添加故障、回滚或恢复阶段。阶段结束后文件退出活跃集合；600 秒是压缩的存储访问时间线，不是实际完成 16 小时预报或写出有效 checkpoint。此次重新分组改变WRF物理布局，不能复用旧READY。

## 4. AI 训练：PERF_002 纯读适配 + 文件级 Zipf

SES 1.2.0 原模板的单个 600 秒 RD，不再划分训练、验证或 checkpoint 角色。
保留原文件大小类别和请求权重：64/128 KiB 小文件承担 60% I/O，1 MiB～1 GiB 大文件承担 40%；小文件请求为 8/32/64 KiB 各三分之一，大文件请求为 1 MiB。源写直接转读，文件内部全部顺序访问。

每个大小类别内采用固定文件排名的 Zipf(0.99)，类别间权重不变；255 个 bin、255 个活跃 FWD，10,000 文件、114.8907470703125 GiB。TV 约 0.577%。

## 5. AI 推理：PERF_003 纯读适配 + 文件级 Zipf

SES 1.2.0 原模板的单个 600 秒 RD，不再赋予文件模型或请求角色，也不划分加载、批量、在线阶段。
原始 20% 顺序写转换为读后，60% 顺序读与 40% 随机读在同一 RD 中并发；两类访问各使用 64/128 KiB 各半，保留文件大小类别间的原请求权重。

对原始逻辑文件按大小类别施加Zipf(0.99)，一个逻辑文件一个桶，再拆成两个等容量物理文件：512MiB→2×256MiB、1GiB→2×512MiB、2GiB→2×1GiB。100个逻辑文件、200个物理文件、100桶、200FWD，合计115GiB。顺序/随机通道共用同一逻辑排名；桶内两个分片均分目标访问质量。

每桶只含一个逻辑文件，消除不同逻辑排名平均化误差；逻辑文件模型TV=0，渲染百分比仍有微小取整误差。基线对逻辑文件均匀选择，每个逻辑文件仍拆成两个分片；两profile共用布局。

这属于PERF文件分片适配：保留逻辑大小和总容量，改变物理大小、文件边界与顺序读取连续长度。每桶两个文件满足现有保守并发校验，但不保证两个FWD始终无争用；实际顺序/随机比例与热度需实测。没有恢复stopafter。

两项 AI 均使用随机文件选择，不设置 stopafter，保留文件内部的顺序/随机访问方式；baseline 只将类别内文件选择改为均匀，其他行为相同。它们是 SES PERF 的纯读研究适配，不执行真实训练、推理或 KV Cache 管理，也不是 SES 标准认证成绩。

## 对照与验收

当前优先运行 `phase_zipf099`。同目录 `baseline` 保持相同阶段、同一布局及组间权重，只将组内文件改为均匀选择，便于隔离 Zipf 的影响。原生基线和先前整体文件 Zipf 均保留，分别回答业务来源结构及全程偏斜的对照问题。

五项分别要求 Accuracy≥90%、Precision≥85%、Recall≥85%，并报告整体汇总；项目最终 Accuracy 下限仍为 80%。原有 HP 标签与阈值不改，阶段切换、冷启动和最后阶段排空样本均不得从主指标中剔除。阶段间不 reset HP，才能观察冷却和复热；每项用例开始前由矩阵入口按既有流程 reset。

文件 Zipf 不保证对象级热样本比例或分类目标。应另报阶段实际 IOPS/字节吞吐、文件/对象覆盖与未来窗口复访分布；`max` 下各阶段实际请求量由存储性能决定，不能按时长简单平均指标。评分工具仍为 `/home/chris/ceph-tool/heat_predictor/evaluation/acceptance_hotcold.py`，主指标合并原始 TP/FP/TN/FN；完整性还需 Trace/MGR 一致、所有 OSD 覆盖、队列排空、无 drop。

## 当前状态与执行交接

本次只生成配置并做离线验证，没有造数据、改 Ceph 数据、清理旧数据、运行真实压测或 commit/push。Baleen四窗对照与GraphChi仍用 `/mnt/cephfs/single_business_phase_v1`；AI训练用 `/mnt/cephfs/single_ses_perf_zipf_v1`；WRF和AI推理改用 `/mnt/cephfs/single_structural_zipf_v2`，本轮没有创建该数据目录。AI 分桶变化，旧布局与 READY 不能复用。上次只读检查 CephFS 剩余约 191.96 GiB，此数字仅供历史参考；造数前必须重新检查空间。不能直接再放一份完整 597.89 GiB，也不能未经用户授权删除旧目录。

离线重生成（在 `/home/chris/ceph-test`）：

```bash
for case in baleen graphchi; do
  python3 -m workload_common.single_v2 render --case "$case" --design phase_zipf \
    --output-root /home/chris/ceph-test/SINGLE_workload/business_phase \
    --data-root /mnt/cephfs/single_business_phase_v1 --rate max
done
for case in ai_training; do
  python3 -m workload_common.single_v2 render --case "$case" --design phase_zipf \
    --output-root /home/chris/ceph-test/SINGLE_workload/business_phase \
    --data-root /mnt/cephfs/single_ses_perf_zipf_v1 --rate max
done
for case in wrf ai_inference; do
  python3 -m workload_common.single_v2 render --case "$case" --design phase_zipf \
    --output-root /home/chris/ceph-test/SINGLE_workload/business_phase \
    --data-root /mnt/cephfs/single_structural_zipf_v2 --rate max
done
```

只读准备前置检查：

```bash
python3 -m workload_common.single_v2 preflight --case all \
  --output-root /home/chris/ceph-test/SINGLE_workload/business_phase
```

矩阵预览：

```bash
/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --dry-run \
  --workload-profile phase_zipf099 \
  --config-root /home/chris/ceph-test/SINGLE_workload/business_phase
```

实际 prepare/run 仍需用户明确授权，指定相同配置目录及全新结果目录。复测须使用 `VDBENCH_HOME=/home/chris/ceph-tool/runtime/vdbench-fractional-xfer-v1`，AI 使用既有 SES 1.2.0 隔离 Python 与 `SES_SOURCE_ROOT`；原 jar `-s` 通过不能代替小数 xfer runtime。仍需处理 Vdbench 遗留 `no_dismount.txt` 与严格 inventory 的已知冲突，不得跳过 READY 校验。

## 阶段审查与展示

RD 名称、顺序、时长、活跃 FWD 已逐项与 model.json 对照。该一致性只证明按设计执行：Baleen 是统计窗口；GraphChi/WRF 是结构与事件顺序的定时适配；AI 保留 PERF 单 RD 混合访问，没有自定义业务生命周期。Zipf 抽样与纯读转换意味着完整扫描、真实计算和写出有效结果不在本负载保证范围内。

旧展示与审计位于 `/home/chris/ceph-tool/results/workload-design-showcase-20260915/`（其中 AI 多阶段设计已废止，不可用作当前配置说明）；更新展示位于 `/home/chris/ceph-tool/results/workload-design-showcase-20260916/`，含六页 `workload-design.pdf`、总览与五项逐阶段 PNG/SVG、`showcase-data.json`。图表从渲染后的 FWD skew 和文件数计算；热图为固定文件顺序的平均请求概率，曲线仅统计活跃文件。颜色是设计概率而非 HP 实测标签，max 下不按阶段时长估算全程请求占比。

2026-09-17 注意：上述2026-09-16展示是历史版本，未包含当前WRF重分组、推理逻辑文件分片或Baleen静态入口，不应作为当前配置图示。
