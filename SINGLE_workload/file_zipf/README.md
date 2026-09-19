> 当前主方案已改为 [business_phase](../business_phase/README.md) 的业务阶段 + 条件 Zipf；本目录保留作全程整体文件 Zipf 对照。

# 整体文件级 Zipf（2026-09-15）

用户决定：使用整体 Zipf，作用于文件；不添加 60% 热池，不强制对象热点。每个用例独立对全体文件使用 `p(r)=r^-0.99 / sum(k^-0.99)`，不是五项混为一个排名，也不是在大小类别内分别归一化。

## 排名、分组和概率

- 所有原始文件都保留：文件数、大小分布及总容量不变；没有新建热文件、缩小业务文件或固定读取文件头的策略。
- 固定种子 `single-file-zipf-v1`，对 `seed/case/original_bin/file_index` 做 SHA-256 排序得到全局 rank，与容量、类别、预测结果无关。种子未按准确率挑选，实测前冻结。
- 全局前 32 个 rank 用单文件 bin；其余相近概率文件在原业务分组和同大小约束下合并。每个 bin 权重等于成员文件的理论概率之和，bin 内均匀随机选文件。这是可量化的 Zipf 近似，不是逐文件精确 Zipf（推理 100 文件例外，为精确分配）。前 32 个文件仍遵循同一 Zipf 公式，无额外保底流量或热池占比。
- `model.json` 每个 bin 的 `source_members` 列出 `[原 bin, 原零起始文件序号, 全局 rank]`；列表顺序对应新 bin 文件序号。可以完整追溯原文件身份。
- 每次选中文件只执行一次 I/O（`stopafter=1`），随后重新随机选文件。否则完整扫描大文件会让文件选择概率与 I/O 请求概率不同。文件内部偏移仍使用 Vdbench 的顺序/随机行为，不构造对象偏移热点。
- 请求速率 `fwdrate=max`、600 秒、纯读。文件级访问概率不保证对象级冷热比例，更不保证分类指标达标。

| 用例 | 文件数 | GiB | 每 RD 的 FWD | TV 概率误差 | 前 1% 文件请求占比（近似） |
|---|---:|---:|---:|---:|---:|
| Baleen | 29819 | 188.279296875 | 245 | 1.584% | 56.34% |
| GraphChi | 2048 | 128 | 243 | 1.345% | 43.44% |
| WRF | 1792 | 112 | 250 | 1.668% | 42.34% |
| SES 训练 | 10000 | 114.8907470703125 | 252 | 0.933% | 51.78% |
| SES 推理 | 100 | 115 | 100 | 0% | 18.89% |
| 合计 | 43759 | **658.1700439453125** | 均 ≤256 | | |

TV 定义为 `0.5 * sum(abs(实际 bin 内均匀概率 - 理论文件概率))`，构建时要求不超过 2%。上表是渲染百分比舍入前的解析结果，有限时长实际请求分布仍需检查。前 1% 文件数向上取整；它是 Zipf 自然产生的集中度，不是另设流量配额。概率舍入由既有精确和为 100 的渲染器处理。

## FWD 预算与请求速率

当前每 RD 的 FWD 预算为 **256**，不再追求接近 Vdbench 的 512 上限。减少 bin 会增加均匀近似误差，当前最大 TV 为 1.668%；原文件身份和 rank 不变。配置文件内 FWD 定义总数也不超过 256（推理两阶段共 200，准备文件最多 252 个 bin 加一个 format 默认定义）。准备 RD 仍每批 20 个 FWD。

用户已明确选择 **`fwdrate=max`**，作为当前五项文件 Zipf 测试的速率设置；不再固定为 100 IOPS。它表示不设置固定目标操作率，实际速率由客户端和存储共同决定。依据：[Oracle 用户指南 1.28.2](https://www.oracle.com/technetwork/server-storage/vdbench-1901683.pdf)。

正式报告应记录实际 IOPS、字节吞吐及各阶段速率。相同文件 Zipf 在不同实际速率下，固定标签窗口内的复访次数仍可能不同。当前更改仅涉及速率，不改变文件布局、排名或 FWD 数量；后续重生成使用下方显式 `--rate max` 命令。

## 保留哪些业务特征，改变哪些特征

文件大小和业务分组保留。请求大小直方图按原生基线的运行时间、速率和请求权重汇总，并保留在相应业务分组/大小内。Baleen 随机读；GraphChi、WRF 和训练为顺序读。推理保持整体 64/128 KiB 各半，并将顺序/随机 60:40 改为 360 秒顺序、240 秒随机两个阶段，避免单文件 bin 同时被多个 FWD 独占；两阶段全局文件概率相同。

**全体文件在各阶段均可被选择。** 因此这套版本不再复现 PSW 的分阶段活跃窗口，也不再复现 WRF input/history/restart 时间线。全局文件 Zipf 还会改变原来各文件大小类别的总体请求份额：不能同时声称仍严格保留 SES 模板的类别操作比例。它是具有相应数据和 I/O 特征的整体文件 Zipf 研究负载，不是自然业务访问的证据，也不是 SES 官方认证。

原生业务基线仍在上一层五个用例目录。新目录的 `run_baseline.vdb` 是同一新布局上的**均匀文件概率对照**，供排除布局差异；它不等于原生基线。正式新方案必须显式指定 `--profile file_zipf099`。

## 渲染和预览（只读数据）

在 `/home/chris/ceph-test` 执行：

```bash
python3 -m workload_common.single_v2 render --case all --design file_zipf \
  --output-root /home/chris/ceph-test/SINGLE_workload/file_zipf \
  --data-root /mnt/cephfs/single_file_zipf_v1 --rate max

/home/chris/ceph-tool/heat_predictor/run_hp_matrix.sh --dry-run \
  --workload-profile file_zipf099 \
  --config-root /home/chris/ceph-test/SINGLE_workload/file_zipf
```

## 给造数据 agent

本次只修改代码和配置，没有造数、删除旧数据或执行压测。新 bin 分组与旧布局不同，旧 READY 不可复用，也不能只把原目录改名。当前准备工具要求完整新目录；两份约 658 GiB 数据不一定能同时放下。先核对空间，再由用户决定旧数据处置或授权专门的文件重排方案，不得自动清理或直接启动造数。

只读准备前置检查：

```bash
python3 -m workload_common.single_v2 preflight --case all \
  --output-root /home/chris/ceph-test/SINGLE_workload/file_zipf
```

实际准备和测试仍需用户明确授权。准备使用现有 CLI `prepare --execute`，指定上述 output-root 及全新 results；正式测试使用矩阵 `--execute --collect-trace --workload-profile file_zipf099 --config-root ...`，另指定全新结果目录。

实际运行必须使用首轮验证过的小数 xfer runtime：`VDBENCH_HOME=/home/chris/ceph-tool/runtime/vdbench-fractional-xfer-v1`；原 jar `-s` 只保证语法通过，不能排除小数直方图运行缺陷。两项 AI 继续使用 `/home/chris/ceph-tool/.venv-ses120/bin/python` 与既有 SES 1.2.0 的 `SES_SOURCE_ROOT`。后续重复测试需要检查 Vdbench 遗留 `no_dismount.txt` 与严格 inventory 的已知冲突，不能跳过 READY。

## 验收

五项各自 Accuracy≥90%、Precision≥85%、Recall≥85%，另报合并混淆矩阵汇总。项目最终 Accuracy 下限 80% 不替代当前单机目标。评分使用原有未来窗口实际标签，不使用 Zipf rank 或文件分组作标签，不排除冷启动和边界误判。

使用 `/home/chris/ceph-tool/heat_predictor/evaluation/acceptance_hotcold.py`，传五个 `--trace case=/absolute/trace/path`。该工具仅检查指标门槛，另需核对完整时长、OSD 范围、Trace 与 MGR 一致、队列清空及无 drop。报告实际请求分布、热点文件对应的对象复访和覆盖情况，不因未达到分类目标而改标签或挑选最好一次重复。

**新版本尚未实测，达标状态未知。** 旧 60% 热池已从负载代码/配置入口撤出，历史产物保存在 `/home/chris/ceph-tool/results/hotcold-design-20260915/retired-60pct-pool/`，不再作为当前造数任务。
