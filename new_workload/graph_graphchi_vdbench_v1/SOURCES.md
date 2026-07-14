# 来源与映射说明

## 主来源：GraphChi OSDI 2012

- 论文页面：<https://www.usenix.org/conference/osdi12/technical-sessions/presentation/kyrola>
- 论文 PDF：<https://www.usenix.org/system/files/conference/osdi12/osdi12-final-126.pdf>

本 workload 只采用 GraphChi 的存储访问思想，不运行 GraphChi 程序：

- GraphChi 面向单机磁盘上的大图计算。
- Parallel Sliding Windows 将图划分为 shard/interval。
- 处理当前 interval 时，当前 shard 通过 `readFully()` 完整读入，成为 memory-shard。
- 其他 shard 通过 `readNextWindow(a,b)` 读取 sliding window。
- 论文说明 window length 会随图的 degree distribution 变化，因此 v1 不手写固定热点比例。
- PageRank 等算法可以执行多轮迭代；当前缩放负载保留第一轮完整 interval 序列，并截取第二轮 interval 0，用于观察 `shard_00` 复热。

## 执行工具：Vdbench

- Oracle Vdbench 下载页和用户手册入口：<https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

本 workload 使用 Vdbench 的：

- FSD：把每个 GraphChi shard 映射成一个文件池；
- FWD：定义每个 shard 在当前阶段的顺序读访问；
- RD：定义 GraphChi execution interval；
- `skew`：使用 `derive_profile.py` 计算得到的每阶段 shard 访问占比；
- `format=(clean,only)` / `format=(restart,only)`：只在 `prepare_data.vdb` 中使用，用于单独造数据。

## generated graph 的角色

论文没有给出可直接用于 vdbench 的 shard 访问百分比。因此 v1 的比例来自：

```text
generated graph 的边分布 + GraphChi PSW readFully/readNextWindow 规则
```

默认图由 [scripts/generate_graph.py](scripts/generate_graph.py) 生成：

- 4 个 interval；
- 每个 interval 128 个顶点；
- 每个顶点生成固定数量的本 interval 边和跨 interval 边；
- 输出边列表为 [datasets/smoke_edges.tsv](datasets/smoke_edges.tsv)。

这些边生成规则不是生产图统计结论，只是受控输入。它的作用是让 `skew` 来自可复算的图结构，而不是手写经验比例。

## 比例推导规则

比例由 [scripts/derive_profile.py](scripts/derive_profile.py) 计算。

对每个 execution interval `p`：

| GraphChi 规则 | 计算方式 | Vdbench 映射 |
|---|---|---|
| `shard[p].readFully()` | 所有 `dst` 属于 interval `p` 的边 | memory-shard 的 FWD 读流 |
| `shard[s].readNextWindow(a,b)` | `src` 属于 interval `p` 且 `dst` 属于 interval `s` 的边，`s != p` | sliding-shard 的 FWD 读流 |
| interval 轮换 | `p=0..P-1` | 多个 RD 顺序执行 |
| 下一轮重新处理 interval 0 | 再次应用 interval 0 的同一 PSW 规则 | `iter2_i0` 中 `shard_00` 复热 |

每个阶段的 `skew` 由各 shard 的派生 read_edges 归一化得到：

```text
skew(shard s)
  = read_edges(shard s) / sum(read_edges(all shards in phase))
```

整数化时使用最大余数法保证每阶段比例合计为 100。

## 保留与舍弃

保留：

- shard 级对象；
- memory-shard 与 sliding-shard 角色；
- 一轮内完整的 interval 顺序轮换；
- 第二轮 interval 0 的单点复热；
- 可由 generated graph 重新计算的 FWD/RD/skew。

舍弃：

- PageRank 数值计算；
- 顶点更新和收敛逻辑；
- GraphChi 原生 shard 文件格式；
- 完整的第二轮 interval 序列；
- 真实生产图比例声明；
- 外部冷热真值表。

因此本 workload 应称为“基于 generated graph 和 GraphChi PSW 规则派生的 vdbench 冷热识别测试”，不能称为完整 GraphChi benchmark，也不能把默认 generated graph 的比例泛化为真实图计算比例。`iter2_i0` 符合多轮迭代重新从 interval 0 开始的执行顺序，但为控制总时长而在此截断属于测试工程设计，不是论文给出的固定五阶段模型。
