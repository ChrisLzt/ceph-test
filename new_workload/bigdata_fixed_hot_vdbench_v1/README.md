# BigData Fixed-Hot Vdbench v1

这是一个 run-only 固定热点负载，用来排除热点迁移对冷热识别模型的影响。

它复用现有数据集：

```text
/mnt/cephfs/bigdata_mapreduce_vdbench_v1
```

不包含造数据或 `format=` 指令。运行前需要先确保
`bigdata_mapreduce_vdbench_v1` 的数据已经存在。

## 访问模型

四个阶段都固定 `pool_01` 为热点：

| 阶段 | pool_01 | pool_02 | pool_03 | pool_04 |
|---|---:|---:|---:|---:|
| `fixed_a_1` | 85% | 1% | 1% | 13% |
| `fixed_a_2` | 85% | 1% | 1% | 13% |
| `fixed_a_3` | 85% | 1% | 1% | 13% |
| `fixed_a_4` | 85% | 1% | 1% | 13% |

数据池容量与主大数据负载一致：`pool_01~03` 各 400 个 12 MiB 文件，`pool_04` 为 8800 个 12 MiB 文件。不存在 `pool_05`。

默认参数与 `bigdata_mapreduce_vdbench_v1` 对齐：

- `xfersize=1m`
- `fileio=sequential`
- `fileselect=random`
- `threads=16`
- `fwdrate=max`
- 四个阶段各 150 秒，总时长 10 分钟

## 运行

```bash
./validate_model.sh
./run_test.sh
```

可覆盖参数：

```bash
PHASE_SECONDS=60 FWD_RATE=800 THREADS=16 ./run_test.sh
OUTPUT_DIR=/tmp/fixed_hot_out ./run_test.sh
```

## 解释

- 如果固定热点效果明显好于 `bigdata_mapreduce_vdbench_v1`，说明模型对热点迁移或概念漂移处理不足。
- 如果固定热点仍然差，问题更可能在特征、标签、概率校准或动态阈值本身。
