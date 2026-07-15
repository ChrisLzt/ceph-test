# SYSU AI 推理 KV cache 负载

这是单节点 AI 推理模型的 750 GiB 物理版本。来源与适用范围见
[`../../new_workload/ai_inference_kvcache_vdbench_v1/README.md`](../../new_workload/ai_inference_kvcache_vdbench_v1/README.md)。

kv_active、kv_next、kv_prefix 各 800 单元、250 GiB、80 rank；每 rank 10
单元、3.125 GiB，包含 160/80/40/20/10 个 4/8/16/32/64 MiB 文件。

六个逻辑预算各 100 秒：active prefill/decode、next prefill/decode、prefix
primary/shifted。active 与 next 各自的 prefill/decode 均保持 rank 1 最热，
prefix primary 为 rank 1 最热，shifted 为 rank 2 最热；所有边界直接切换。
prefill 为顺序读，decode 与 prefix 为随机读。每个固定大小档独立计算
Zipf(0.99)，全部为 4 MiB Direct I/O、
`fwdrate=max`，合计仍为 600 秒。

数据目录为 `$ANCHOR_ROOT/ai_inference_kvcache_vdbench_v1`；配置不含 `hd=`。
