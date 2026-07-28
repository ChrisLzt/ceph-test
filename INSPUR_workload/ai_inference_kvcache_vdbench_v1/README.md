# INSPUR AI 推理 KV cache 负载

这是 INSPUR 套件中 3000 GiB 的 AI 推理物理版本。来源与适用范围见
[`../../new_workload/ai_inference_kvcache_vdbench_v1/README.md`](../../new_workload/ai_inference_kvcache_vdbench_v1/README.md)。

kv_active、kv_next、kv_prefix各800单元、1000 GiB。每组以100个参考rank计算
Zipf并压缩为40个物理bin：前20个各8单元、10 GiB，后20个各32单元、40 GiB。

六个逻辑预算各 100 秒：active prefill/decode、next prefill/decode、prefix
primary/shifted。active 与 next 各自的 prefill/decode 均保持 rank 1 最热，
prefix primary 为 rank 1 最热，shifted 为 rank 2 最热；所有边界直接切换。
prefill 顺序写入新生成并下沉到 CephFS 的 KV cache，decode 与 prefix 随机
读取已有 cache，阶段序列为 `W → R → W → R → R → R`。每个固定大小档独立计算
Zipf(0.99)，每阶段200 FWD。全部为4 MiB Direct I/O、`fwdrate=max`，合计仍为
600秒。

该读写划分来自 MLPerf Storage KV Cache 的 write-heavy prefill 与 read-heavy
decode 模型：
<https://github.com/mlcommons/storage/blob/main/kv_cache_benchmark/DESIGN.md>。

数据目录为 `$ANCHOR_ROOT/ai_inference_kvcache_vdbench_v1`；配置不含 `hd=`。
