# GraphChi 图计算冷热负载 vdbench v1

## 1. 用途

本负载用于验证存储系统能否识别图计算中的 shard 级移动热点：

- 当前 GraphChi execution interval 对应的 memory-shard 升温；
- sliding shards 产生由图结构决定的背景访问；
- interval 轮换后热点迁移；
- 下一轮迭代中旧 shard 复热。

它不运行 GraphChi 程序，而是使用 GraphChi 论文中的 Parallel Sliding Windows 访问规则，把一张确定性 generated graph 转换成 vdbench workload。

## 2. 权威来源

主要来源：

- Kyrola、Blelloch、Guestrin，*GraphChi: Large-Scale Graph Computation on Just a PC*，OSDI 2012。
- 论文页面：<https://www.usenix.org/conference/osdi12/technical-sessions/presentation/kyrola>
- 论文 PDF：<https://www.usenix.org/system/files/conference/osdi12/osdi12-final-126.pdf>

工具来源：

- Oracle Vdbench：<https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

详细映射见 [SOURCES.md](SOURCES.md)。

## 3. 负载逻辑

GraphChi 论文 Algorithm 3 的关键规则：

- 当前 interval `p` 的 `shard[p]` 通过 `readFully()` 完整读入，成为 memory-shard。
- 非当前 shard 通过 `readNextWindow(a,b)` 读取 sliding window。
- sliding window 的长度依赖图的 degree distribution，因此不手写固定热点比例。

本实现的工作流是：

```text
生成图 -> 按 GraphChi PSW 规则计算比例 -> 渲染 vdbench -> 分开造数据/跑测试
```

比例计算方式：

```text
memory_shard_edges(p)
  = dst 属于 interval p 的所有边

sliding_window_edges(p, s)
  = src 属于 interval p 且 dst 属于 interval s 的边，s != p

skew(p, s)
  = shard_edges(p, s) / sum(shard_edges(p, *))
```

因此 vdbench `skew` 的来源是 `generated graph 的边分布 + GraphChi PSW readFully/readNextWindow 规则`，不是经验比例。

默认 generated graph 写入 [datasets/smoke_edges.tsv](datasets/smoke_edges.tsv)。默认参数：

| 参数 | 默认值 |
|---|---:|
| intervals | 4 |
| vertices_per_interval | 128 |
| iterations | 2 |
| files_per_shard | 1800 |
| file_size | 16 MiB |
| 总容量 | 约 112.50 GiB |

## 4. 文件结构

- [scripts/generate_graph.py](scripts/generate_graph.py)：生成确定性 generated graph。
- [scripts/derive_profile.py](scripts/derive_profile.py)：根据边分布和 PSW 规则生成 vdbench 模板。
- [configs/prepare_data.vdb.in](configs/prepare_data.vdb.in)：只造数据的模板。
- [configs/run_test.vdb.in](configs/run_test.vdb.in)：只跑正式阶段的模板。
- `rendered/prepare_data.vdb`：渲染后的造数据配置。
- `rendered/run_test.vdb`：渲染后的正式测试配置。
- [prepare_data.sh](prepare_data.sh)：只执行 clean/create。
- [run_test.sh](run_test.sh)：只执行正式测试，不包含 `format=`。
- [validate_model.sh](validate_model.sh)：重新渲染并校验模型。

本目录不提供外部冷热真值表。冷热判断由使用者结合阶段、shard 访问统计和被测系统观测自行判断。

## 5. 生成配置

```bash
cd /home/chris/ceph-test/new_workload/graph_graphchi_vdbench_v1
./render_config.sh
```

默认生成两个独立配置：

- `rendered/prepare_data.vdb`：只包含 `prepare_clean` 和 `prepare_create`。
- `rendered/run_test.vdb`：只包含 `iter1_i0` 到 `iter2_i3` 正式阶段；不包含任何 `format=`。

也可以只渲染其中一个：

```bash
./render_config.sh prepare
./render_config.sh run
```

常用环境变量：

```bash
ANCHOR=/mnt/cephfs/graph_graphchi_vdbench_v1 \
VDBENCH_HOME=/home/chris/PDSL/vdbench \
REMOTE_USER=chris \
HOST1=s52.servers.hustpdsl.cn \
PHASE_SECONDS=75 \
FWD_RATE=1000 \
THREADS=16 \
FILES_PER_SHARD=1800 \
FILE_SIZE=16m \
XFER_SIZE=1m \
INTERVALS=4 \
VERTICES_PER_INTERVAL=128 \
ITERATIONS=2 \
./render_config.sh
```

默认数据路径为 `/mnt/cephfs/graph_graphchi_vdbench_v1`，不再添加 `new_workload/` 中间层。默认 Vdbench 目录为 `/home/chris/PDSL/vdbench`，默认只使用当前单节点 `s52.servers.hustpdsl.cn`。

## 6. 执行

运行前先检查参数和容量：

```bash
./validate_model.sh
```

第一次造数据：

```bash
./prepare_data.sh
```

`prepare_data.sh` 会渲染并执行 `rendered/prepare_data.vdb`。其中 `prepare_clean` 通过 `format=(clean,only)` 清理旧结构，`prepare_create` 通过 `format=(restart,only)` 创建约 112.50 GiB 文件。这个脚本会清理/重建数据，只应在需要重新造数时运行。

后续正式测试：

```bash
./run_test.sh
```

`run_test.sh` 会渲染并执行 `rendered/run_test.vdb`。该配置没有 `format=`，不会执行 clean/create，不会重新造数据。默认正式测试包含 8 个阶段，每阶段 `PHASE_SECONDS=75`，总时长约 10 分钟。

## 7. 验收

负载符合度：

- `validate_model.sh` 通过；
- Vdbench `-s` 能解析 `prepare_data.vdb` 和 `run_test.vdb`；
- `run_test.vdb` 中没有 `format=`；
- 每个正式阶段的 FWD `skew` 合计为 100；
- `skew.html` 中各 shard 实际 share 与目标相差不超过 2 个百分点。

冷热识别：

- 每个 `iterX_iY` 中，`shard_Y` 是 memory-shard，通常应是该阶段主要热点；
- 其他被访问 shard 是 sliding-shard，热度由边分布决定；
- 第二轮迭代用于观察旧 shard 复热；
- 记录 time-to-promote、time-to-demote、time-to-reheat、迁移字节和 P95/P99 时延。

## 8. 已知边界

- 本负载适合评价 shard 级冷热识别，不等价于完整 GraphChi benchmark。
- 默认 generated graph 是受控输入，不代表生产图分布。
- 本负载不模拟 GraphChi 原生 shard 文件格式、PageRank 数值计算、顶点更新或收敛。
- 如果获得真实图边列表，应替换 `EDGE_FILE` 后用同一 `derive_profile.py` 重新计算比例。
