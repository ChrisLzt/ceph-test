# AI 负载 trace 比例替换方案

本文记录未来用公开或目标系统 trace 替换当前 Zipf(0.99) 的方法，不是当前
脚本执行说明。

## 当前基线

目前没有找到一个公开、权威且可直接下载的 AI 文件级存储 trace，能够同时给出
对象容量、对象访问次数和明确的训练或推理语义。现有来源主要支持生命周期：

- Meta DSI / ISCA 2022：训练数据反复读取且 feature/sample 访问存在偏斜；
- vLLM/PagedAttention / SOSP 2023：KV cache 动态增长、decode 持续使用并可
  跨请求共享；
- MLPerf Storage / DLIO：提供训练存储、checkpoint 和 KV cache benchmark
  语义，但参数不等于真实线上冷热比例。

AI训练和AI推理均先将每个数据组划分为100个等容量参考rank，再保留前20个、
将后80个每4个合并，形成40个物理bin。
每个固定文件大小档
按真实文件数量独立计算 Zipf(0.99)，再把连续文件概率聚合到 rank，以十进制
小数写入 Vdbench。没有整数化、最小 1% 或全程不访问的数据。

单节点当前布局：

- AI 训练：dataset/current/old 为 2000/200/200 单元，即
  93.75/9.375/9.375 GiB；
- AI 推理：active/next/prefix 各 800 单元，即各 37.5 GiB；
- 文件大小为 4/8/16 MiB，每单元 48 MiB。

SYSU 使用相同单元数和 rank 逻辑，但每单元为 320 MiB，文件大小为
4/8/16/32/64 MiB，总容量 750 GiB。

Zipf(0.99) 是 YCSB 常用 popularity 参数，只是可复现的临时执行模型，不是
Meta DSI 或 PagedAttention 的实测冷热比例。

## AI 训练 trace 路线

1. 选择 Criteo Terabyte、DLRM/MLPerf DLRM 或目标系统访问记录；
2. 按 sample ID、categorical feature ID 或 embedding ID 统计访问频次；
3. 获得或明确假设每个 ID 的存储容量；
4. 按频次降序，并按等容量聚合到100个参考rank，再按当前20%头部保留规则
   聚合为40个物理bin；
5. 同时输出每个参考rank及物理bin的容量、访问次数、访问占比和累计访问占比；
6. 用 trace 权重替换 dataset 的 Zipf 权重，同时保留 checkpoint 生命周期。

如果只有 feature 频次而没有真实容量，文档必须写明“由公开数据集访问频次与
等容量假设推导”，不能称为 CephFS 生产存储 trace。

## AI 推理 trace 路线

1. 获取 request/session/prefix trace；
2. 将 prefix、session 或 KV block 映射到带容量的 cache 对象；
3. 统计 prefill、decode 和 prefix reuse 中每对象读取次数；
4. 按容量聚合到 active/next/prefix 各100个参考rank，再压缩为40个物理bin；
5. 计算每阶段 rank 访问占比，并替换当前 Zipf 权重；
6. 保留 prefill/decode 模式切换与数据组迁移语义。

## 建议工具接口

后续可增加 `new_workload/tools/trace_profile.py`：

```text
--trace PATH
--mode sample-id | feature-id | prefix-id | custom-csv
--rank-count 100
--output ratios.csv
```

输出至少包含：

```text
rank,capacity_bytes,capacity_pct,access_count,access_pct,cumulative_access_pct
```

采用 trace 后，对应 README 必须记录 trace 名称、来源、字段、容量换算假设、
聚合方法和最终 Vdbench 权重。
