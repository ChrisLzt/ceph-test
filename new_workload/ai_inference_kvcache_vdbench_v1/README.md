# AI 推理 KV cache vdbench 冷热识别负载 v1

这个负载不运行真实 LLM，也不评价 token 生成速度。它把 LLM 推理系统中 KV cache 的明确读写行为映射成 vdbench 对 CephFS 的阶段化读写，用于冷热识别。

核心逻辑：

- prefill 阶段生成/写入当前请求的 KV cache；
- decode 阶段反复读取已有 KV cache；
- 下一批请求会生成新的 KV cache，热点迁移；
- 共享前缀或多轮对话会复用旧 KV cache；
- 冷 KV cache 长期不访问，作为对照。

## 来源

主来源：

- vLLM/PagedAttention：`Efficient Memory Management for Large Language Model Serving with PagedAttention`，SOSP 2023。论文说明 LLM serving 中 KV cache 很大、动态增长，并在生成阶段被持续使用；PagedAttention 用块化方式管理 KV cache，并支持跨请求/分支的 cache sharing。

补充来源：

- MLPerf Storage KV Cache：MLCommons Storage 中针对 KV-cache I/O 的官方 benchmark 类别，用于说明 KV cache 已被 MLPerf Storage 纳入存储侧 benchmark 范围。

本目录使用 vdbench 执行这些读写阶段。vdbench 不是负载来源，只是把设定好的文件读写模型落到 CephFS 上。

详细映射见 [SOURCES.md](SOURCES.md)。

## 默认数据路径和容量

默认数据路径：

```text
/mnt/cephfs/ai_inference_kvcache_vdbench_v1/
```

默认容量为 112 GiB：

| 数据集 | 文件数 | 单文件大小 | 容量 | 作用 |
|---|---:|---:|---:|---|
| `kv_active` | 32 | 1 GiB | 32 GiB | 当前请求/会话 KV cache |
| `kv_prefix_reuse` | 32 | 1 GiB | 32 GiB | 旧 KV cache，prefix reuse 阶段复热 |
| `kv_next` | 32 | 1 GiB | 32 GiB | 下一批请求 KV cache，热点迁移目标 |
| `kv_cold` | 16 | 1 GiB | 16 GiB | 不访问的冷 KV cache |

这些容量是当前单节点 CephFS 100–120 GiB/负载预算下的缩放值，不声称来自论文的固定容量比例。

## 工作流

```bash
cd /home/chris/ceph-test/new_workload/ai_inference_kvcache_vdbench_v1

./validate_model.sh
./prepare_data.sh
./run_test.sh
```

含义：

- `render_config.sh`：根据当前环境变量渲染 vdbench 配置。
- `prepare_data.sh`：只造数据，运行 `rendered/prepare_data.vdb`，包含 `format=(clean,only)` 和 `format=(restart,only)`。
- `run_test.sh`：只跑测试，运行 `rendered/run_test.vdb`，不包含任何 `format=`。
- `validate_model.sh`：只做本地配置和模型检查，不写 CephFS。

数据已经造好后，重复冷热测试只执行：

```bash
./run_test.sh
```

不要每次测试前重复运行 `prepare_data.sh`，否则会重置数据历史。

## 测试阶段

```text
prefill_write_active
-> decode_read_active
-> prefill_write_next
-> decode_read_next
-> prefix_reuse_read_old
```

- `prefill_write_active`：模拟当前请求 prefill 产生 KV cache。
- `decode_read_active`：模拟 decode 阶段反复读取当前 KV cache。
- `prefill_write_next`：模拟下一批请求产生新的 KV cache，热点开始迁移。
- `decode_read_next`：模拟下一批请求 decode，`kv_next` 成为热点。
- `prefix_reuse_read_old`：模拟共享前缀/多轮对话复用旧 KV cache，旧数据复热。

`kv_cold` 在测试阶段不读写，用于观察冷数据能否保持冷状态。

## 可调参数

```bash
ANCHOR=/mnt/cephfs/ai_inference_kvcache_vdbench_v1 \
THREADS=8 \
FORMAT_THREADS=4 \
PHASE_SECONDS=120 \
FWD_RATE=1000 \
KV_READ_XFER_SIZE=1m \
KV_WRITE_XFER_SIZE=4m \
./render_config.sh all
```

默认正式测试包含 5 个阶段，每阶段 `PHASE_SECONDS=120`，总时长约 10 分钟。默认 `THREADS=8`，允许多线程，但避免旧 Python proxy 那种大对象并发写入导致单节点 CephFS 被打满。单节点 SN350 上如果 Ceph 出现 backfill、recovery 或 slow ops，应先停止测试，等 `ceph -s` 恢复 `active+clean` 后再运行。

## 边界

- 这不是正式 MLPerf Storage 结果。
- 这不是 LLM 推理性能 benchmark。
- 论文和官方 benchmark 提供读写语义；vdbench 的 `xfersize`、线程数、容量缩放是当前实验环境参数。
