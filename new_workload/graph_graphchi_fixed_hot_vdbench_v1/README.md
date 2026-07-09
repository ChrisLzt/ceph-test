# GraphChi 固定热点负载

这个目录用于验证 GraphChi 原负载 accuracy 偏低是否主要来自热点迁移。

它复用 `graph_graphchi_vdbench_v1` 的数据集，不重新造数据：

```text
/mnt/cephfs/graph_graphchi_vdbench_v1/shard_00..03
```

正式测试保留 GraphChi 原负载的 8 个 75 秒阶段、1 MiB 传输、16 线程和单节点执行方式，但把热点固定在 `shard_00`：

```text
shard_00 / shard_01 / shard_02 / shard_03 = 75% / 13% / 6% / 6%
```

如果这个固定热点版本明显高于 `graph_graphchi_vdbench_v1`，说明原 GraphChi 低 accuracy 主要来自 PSW 热点迁移和旧热点退潮；如果仍然偏低，则需要继续检查 GraphChi 的顺序读、对象粒度和模型特征。

## 使用

先确保原 GraphChi 数据已经存在，然后运行：

```bash
cd /home/chris/ceph-test/new_workload/graph_graphchi_fixed_hot_vdbench_v1
./validate_model.sh
./run_test.sh
```
