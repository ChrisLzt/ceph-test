# 单节点无热点迁移对照负载

本目录包含 5 个只运行测试、不创建数据的 Vdbench 对照负载。它们复用
`SINGLE_workload` 已经在 `/mnt/cephfs` 下创建的数据，使用固定的 FSD 与
Zipf(0.99) skew，使物理 bin 访问分布不迁移。MapReduce、GraphChi 和 HPC 使用
单个 600 秒 RD，避免阶段重启干扰 object 热度；AI 负载保留原有读模式阶段。

本目录不提供 `prepare_data.sh`。必须先使用 `SINGLE_workload` 对应负载完成造数据；
运行脚本只读取这些文件，并在启动 Vdbench 前检查所有引用目录是否存在。

## 固定热点设计

| 对照负载 | 复用的数据 | 固定热点 | 阶段 |
|---|---|---|---|
| MapReduce | `bigdata_mapreduce_vdbench_v1` | 固定 pool_01 85.41%、background 14.59% | 1 × 600 s |
| GraphChi | `graph_graphchi_vdbench_v1/shard_00` | rank 1 最热 | 1 × 600 s |
| HPC | `hpc_wrf_vdbench_v1/startup` | rank 1 最热 | 1 × 600 s |
| AI 训练 | `ai_training_checkpoint_vdbench_v1/dataset` | rank 1 最热 | 3 × 160 s + 2 × 60 s |
| AI 推理 | `ai_inference_kvcache_vdbench_v1/kv_active` | rank 1 最热 | 6 × 100 s |

固定 bin 只表示长期访问概率不变，不保证每个具体 object 的未来冷热标签恒定。
AI 训练前三阶段为随机读，后两阶段为顺序读；AI 推理保留
`顺序、随机、顺序、随机、随机、随机` 的模式变化。读取方式可以变化，但阶段间
的文件集合和访问 skew 不变。

五套负载均为纯读、4 MiB 请求、Direct I/O、`fwdrate=max`，总时长 600 秒。
它们沿用正式负载的尾部合并：MapReduce为50个参考rank压缩到20个bin，其他
负载为100个参考rank压缩到40个bin。MapReduce RD选择当前热点池和background；
五种负载的每个RD均选择120个FWD。AI重复阶段按读模式复用FWD集合，因此配置
只保留随机读和顺序读各一套定义。

## 使用方式

先验证全部配置：

```bash
cd /home/chris/ceph-test
./no_migration_workload/validate_all.sh
```

运行单个负载：

```bash
./no_migration_workload/ai_inference_no_migration_v1/run_test.sh
```

默认数据根目录为 `/mnt/cephfs`。如已有数据位于其他挂载点，可覆盖：

```bash
ANCHOR_ROOT=/other/cephfs \
  ./no_migration_workload/hpc_wrf_no_migration_v1/run_test.sh
```

可用 `HOST1`、`REMOTE_USER`、`VDBENCH_HOME`、`THREADS`、`FWD_RATE` 和
`OUTPUT_DIR` 覆盖运行参数。不要对该目录执行造数据；它没有任何 clean/create
配置。
