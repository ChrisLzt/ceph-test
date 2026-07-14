# AI 负载冷热比例 trace 提取方案（未来研究）

本文档记录 AI 训练/推理负载中“热数据容量占比、访问占比”的后续替换方案，
不是当前脚本的执行说明。当前参数以两个负载目录中的 README 和渲染配置为准。
下文列出的容量和权重只对应 `new_workload` 单节点版本；750 GiB SYSU 版本的
当前参数见 [`../SYSU_workload/README.md`](../SYSU_workload/README.md)，但未来
获得 trace 后应由同一提取流程分别重新聚合两种容量布局。

当前 AI 训练和 AI 推理脚本没有使用旧版 `hot/warm/cold` 或 80/20 固定热点模型，而是使用 Zipf(alpha=0.99) rank 模型：

- 所有数据分片都会被访问；
- 少量 rank 承担主要访问；
- 长尾 rank 仍保留低频访问；
- Zipf 权重是工程执行模型，不是 AI 论文中的实测比例。

后续如果获得公开 trace 或目标系统 trace，应直接用 trace 提取出的容量/访问比例替换当前 Zipf 权重。

## 1. 当前结论

目前没有找到一个足够权威、公开、可直接下载的 AI 训练/推理“文件级存储访问 trace”，能够同时给出：

- 每个文件、对象、样本或 KV block 的容量；
- 每个文件、对象、样本或 KV block 的访问次数；
- 明确的 AI 训练或 AI 推理语义；
- 可直接换算热数据容量占比和访问占比。

已有权威来源更多提供负载语义，而不是冷热比例：

- Meta DSI / ISCA 2022：说明大规模推荐模型训练会读取、过滤大规模数据集，并存在热门 features/samples，但没有给出可直接落到 CephFS 文件池的 hot/cold 容量与访问比例。
  <https://arxiv.org/abs/2108.09373>
- vLLM / PagedAttention / SOSP 2023：说明 LLM 推理中 KV cache 动态增长、decode 持续使用 KV cache、cache 可共享，但没有给出热 KV cache 的固定容量与访问比例。
  <https://arxiv.org/abs/2309.06180>
- MLPerf Storage / DLIO：提供 AI 存储 benchmark 语义和执行方式，但参数用于 benchmark，不等同于真实线上冷热比例。
  <https://github.com/mlcommons/storage>
  <https://github.com/argonne-lcf/dlio_benchmark>

## 2. 当前临时模型

当前使用 Zipf(alpha=0.99) 作为临时偏斜访问模型。alpha=0.99 来自 YCSB 常用 Zipfian 参数，用于表达“少量对象更热，但长尾对象仍被访问”。

### AI 训练

训练数据容量：

- `dataset_rank_01~20`：20 个等容量 rank；
- 每个 rank 为 250 个 20 MiB 文件，容量约 4.88 GiB；
- 合计约 97.66 GiB；
- 按 4 MiB object 估算，共 25000 个 object。

生成权重：

- 先按 25000 个 object 计算 Zipf(alpha=0.99)；
- 再聚合到 20 个等容量 rank；
- 聚合访问占比约为 `70.9% / 6.7% / 3.9% / 2.8% / 2.2% / 1.8% / 1.5% ...`；
- vdbench 中整数化为 `69/6/4/3/2/2/1×14`。

### AI 推理

KV cache 容量：

- `kv_active_rank_01~20`：约 39.06 GiB；
- `kv_next_rank_01~20`：约 39.06 GiB；
- `kv_prefix_rank_01~20`：约 39.06 GiB；
- 每类 KV cache 20 个 rank，每个 rank 为 100 个 20 MiB 文件，容量约 1.95 GiB；
- 每类按 4 MiB object 估算，共 10000 个 object。

生成权重：

- 先按每类 10000 个 object 计算 Zipf(alpha=0.99)；
- 再聚合到 20 个等容量 rank；
- 聚合访问占比约为 `68.4% / 7.2% / 4.3% / 3.0% / 2.4% / 1.9% / 1.6% ...`；
- vdbench 中整数化为 `68/7/4/3/2/2/1×14`。

## 3. 推荐的 trace 提取路线

### 3.1 AI 训练

推荐路线：

1. 使用 Criteo Terabyte / DLRM / MLPerf DLRM 相关公开数据作为训练访问近似。
2. 按样本 ID、categorical feature ID 或 embedding ID 统计访问频次。
3. 将 ID 按访问频次降序排列。
4. 按固定容量假设或真实特征容量将 ID 聚合成 rank。
5. 计算每个 rank：
   - 容量占比；
   - 访问次数占比；
   - 累计访问占比。
6. 将提取结果写入 vdbench 模板，替换当前 Zipf 权重。

限制：

- 这仍然是“训练数据访问热点”的近似，不是 CephFS 文件级 trace；
- 如果没有每个 ID 的真实存储容量，只能按等容量 ID 或等容量 shard 假设换算容量占比；
- 结论必须在文档中写明“由公开数据集访问频次推导”，不能写成线上存储 trace。

### 3.2 AI 推理

推荐路线：

1. 获取推理请求 trace，提取 request/session/prefix 的重复度。
2. 将 prefix、session 或 KV block 映射为 KV cache rank。
3. 统计每个 rank 被复用或读取的次数。
4. 计算每个 rank 的容量占比和访问占比。
5. 用提取出的比例替换当前 `kv_active` / `kv_next` / `kv_prefix` 的 Zipf 权重。

如果没有真实推理请求 trace，AI 推理负载保持“语义驱动 + Zipf 偏斜模型”：

- prefill 读取造数据阶段预生成的 KV cache；
- decode 读当前 KV cache；
- 下一批请求产生热点迁移；
- prefix reuse 复热旧 KV cache；
- 所有 rank 都被访问，不设置全程不访问数据。

## 4. 建议实现的 trace 工具

后续可以在 `new_workload/tools/` 下增加脚本，例如：

```text
trace_profile.py
```

输入：

```text
--trace PATH
--mode criteo-categorical | sample-id | prefix-id | custom-csv
--rank-count 20
--object-size 4m
--output ratios.csv
```

输出：

```text
rank,capacity_gib,capacity_pct,access_count,access_pct,cumulative_access_pct
rank_01,12,12.5,...
rank_02,12,12.5,...
...
```

然后由渲染脚本读取 `ratios.csv`，生成 vdbench `skew=` 参数。

## 5. 判断标准

在没有 trace 前，当前 Zipf 模型只用于工程验证：

- 是否能把阶段主 rank 识别为热；
- 低频长尾 rank 是否低于主热点；
- 旧热点在后续 epoch / prefix reuse / recovery 阶段是否能复热；
- 没有全程不访问数据时，系统是否仍能区分不同热度等级。

在拿到 trace 后，应以 trace 提取结果为准，并在对应 README 中写清：

- trace 名称；
- trace 来源；
- 提取字段；
- 容量换算假设；
- 访问占比计算方式；
- 生成的 vdbench `skew` 参数。
