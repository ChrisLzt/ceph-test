# 来源和参数映射

## 1. 主要论文

Cristina L. Abad, Nathan Roberts, Yi Lu, Roy H. Campbell, “A Storage-Centric Analysis of MapReduce Workloads: File Popularity, Temporal Locality and Arrival Patterns,” 2012 IEEE International Symposium on Workload Characterization (IISWC), pp. 100–109, DOI: 10.1109/IISWC.2012.6402909.

- DOI：<https://doi.org/10.1109/IISWC.2012.6402909>
- 作者公开全文：<https://assured-cloud-computing.illinois.edu/files/2014/03/A-Storage-Centric-Analysis-of-MapReduce-Workloads-File-Popularity-Temporal-Locality-and-Arrival-Patterns.pdf>
- CCF 目录：IISWC 未被当前 CCF 推荐目录收录；本文仍是基于 Yahoo! 生产
  trace 的同行评审来源，不把它标为 CCF-B。

数据范围：

- Yahoo! PROD：4,146 节点，约 3.83～3.93 PB。
- Yahoo! R&D：1,958 节点，约 2.95～3.63 PB。
- 6 个月 namespace snapshot/audit trace。
- 合计超过 9.4 亿 create 和 120 亿 open。
- trace 只有 namespace metadata，毫秒级时间戳；没有每次 open 的实际 I/O 大小。

## 2. v1 已使用的观测值

| 论文观测 | 位置 | v1 映射 | 偏差/说明 |
|---|---|---|---|
| PROD：年龄不超过 1 天的文件贡献 85.41% accesses | §IV-B/I4 | 当前年轻热点池获得 85.41% operation，background 获得剩余 14.59% | accesses 是 open 次数，不是实测 read bytes；论文没有规定四个池同时访问 |
| PROD：年龄不超过 1 天的文件占 2.21% bytes | §IV-B/I4 | 三个候选热点池各取 2.21% 的原始容量窗口；去除 0 访问 cold 池后归一化为约 4.09%，最终按 2,400 个总单元工程量化为 4.167% | 4.167% 是把论文 cold 容量移除后重新归一化并量化的结果，不是论文原始观测 |
| R&D：年龄不超过 1 天的文件贡献 78.91% accesses、占 1.87% bytes | §IV-B/I4 | 未作为默认 profile | 当前模型只采用 PROD 口径，不与 R&D 参数混用 |
| inactive storage 占 51%～52% 文件 | §IV-A/I1 | 不再单独造 0 访问池 | 当前要求所有测试数据都被访问，因此不直接复现 inactive 文件数 |
| inactive storage 占 42%～46% bytes | §IV-A/I1 | 使用 PROD 口径的 46% 作为 cold 容量；当前把该 46% 按 2.21:2.21:2.21:47.37 分给 A/B/C/背景池 | 论文只给范围；由于访问侧使用 PROD 的 85.41%，容量侧也采用 PROD 侧的 46% |
| file population 高 churn、静态 popularity 模型不足 | §IV-A/I2、§VI | A→B→C→A 热点迁移 | 迁移顺序和阶段时长是工程扩展 |
| file size 与 popularity 没有强相关 | §IV-E/I7 | 每池使用 4/8/16 MiB 三档等容量文件 | 三档大小和等容量规则是受控参数，不是生产文件分布 |

## 3. 已核对但不作为默认容量热度映射的观测值

- PROD top 2.17% 文件贡献 34% open；R&D top 0.47% 文件贡献 39% open（§IV-A/I3）。该数据只描述 open 次数占比，没有给出 read bytes 或访问容量占比，因此不再作为 v1 默认热点强度。
- 论文明确说明 trace 只有 namespace metadata，无法确定每次 open 实际读取了多少字节；因此 v1 只能把 access share 映射为 Vdbench operation share，不能声称模拟了论文中的真实 read-byte share。
- 补充检索的同类 MapReduce workload 论文（例如 Chen, Alspaugh, Katz, “Interactive Analytical Processing in Big Data Systems: A Cross-Industry Study of MapReduce Workloads,” arXiv:1208.4174）主要讨论跨行业 MapReduce job/workload 行为，没有给出可直接映射为“某比例存储容量承载某比例访问字节”的热容量参数。因此 v1 仍使用 Abad 等人的 temporal-locality bytes/accesses 关系作为容量热度来源。

## 4. 论文已给出但当前模型未纳入的特征

以下内容用于明确当前模型的适用范围，不构成后续开发承诺：

### File access frequency

- PROD power-law tail：`alpha=2.99, xmin=937`（6 个月）。
- R&D power-law tail：`alpha=2.36, xmin=325`（6 个月）。
- PROD：15.03% 文件只访问 1 次，68.40% 最多 5 次，80.98% 最多 10 次。
- R&D：23.66% 文件只访问 1 次，84.25% 最多 5 次，90.08% 最多 10 次。

v1 不使用聚合 top-open share 作为默认热点强度，也没有生成完整 power-law/低频
分布。当前100/100/100/2100容量单元来自论文PROD原始容量模型
2.21/2.21/2.21/47.37/46去除0访问cold池后的重分配，并按2,400个总单元量化为
约4.167/4.167/4.167/87.5%。每池先计算50个参考rank，再将前10个单独保留、
后40个每4个合并为10个尾部bin，共20个物理bin。每阶段只生成当前热点池与
background的FWD，不为0%池生成FWD。

### Age at access（AOA）

| Percentile | PROD | R&D |
|---:|---:|---:|
| P50 | 407.80 秒 | 33.53 分钟 |
| P80 | 3.06 小时 | 1.25 天 |
| P90 | 6.11 天 | 13.06 天 |

- v1 只使用 1 天边界处的 PROD access/bytes share，没有实现完整 AOA CDF 或 P50/P80/P90 阶段。

### Age at deletion（AOD）

| Percentile | PROD | R&D |
|---:|---:|---:|
| P50 | 117.1 秒 | 238.51 秒 |
| P80 | 453.36 秒 | 26.61 分钟 |
| P90 | 22.27 分钟 | 1.25 小时 |

这些数据用于未来 create→consume→delete 生命周期版本。

### Arrival burst/self-similarity

- PROD 有 36.5% create 的 interarrival ≤ 1 ms。
- open/create/delete arrivals 均表现出 burst 和 self-similarity。
- 论文建议用能够保留 autocorrelation 的 Markovian Arrival Process，而不是只从独立 CDF 抽样。
- open 第一小时的 Hurst 估计：PROD 0.9370（variance-time）/0.8136（R/S），R&D 0.9020/0.9355。
- create/delete 的 Hurst 值见论文 Table VI。

v1 的固定 `fwdrate` 不代表该 arrival process。

## 5. 工具来源

Oracle Vdbench User Guide 定义了本负载使用的机制：

- FSD `files`/`sizes`：对象池文件数量和大小。
- FWD `operation=read`：data operations。
- FWD `skew`：各对象池获得的总 operation 比例。
- RD `fwdrate=max`：在当前设备可承受范围内尽快发出 operation。
- RD `format=only`：只创建目录/文件结构。
- 保留 skew report 检查实际 workload share；不使用 `abort_failed_skew=2` 硬中止，
  因为 4 MiB、单盘受限的 10 分钟测试无法保证每个 FSD 达到建议的 2000 次操作。

来源等级：A（工具官方文档）。

- <https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

## 6. 不允许的结论

本负载结果不能用于声称：

- 所有大数据 workload 都符合 2%/85%。
- 论文观测到了 2% 容量承载 85% read bytes。
- Yahoo! trace 的文件大小是 12 MiB。
- 当前版本保留了单独的 Yahoo! inactive 文件池，或复现了 Yahoo! inactive 文件数 51%～52%。
- Yahoo! HDFS 使用 1 MiB data request。
- 固定阶段时长等于原 trace 的热点迁移周期。
- data proxy 等价于真实 MapReduce 数据扫描。
