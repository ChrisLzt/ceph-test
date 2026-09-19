# Baleen 原生频率静态 Vdbench（2026-09-17）

全时段原生 GET+PUT 计数合并为一个 `native_all` RD，600 秒、fwdrate=max、纯读、随机文件选择和随机文件内部访问；不设置 stopafter，不施加 Zipf。

## 数据与来源

冻结来源为 Region4/full_0_0.1.trace，来源 SHA-256 与窗口提取规则保存在 model.json/provenance。不是重新下载或逐条按时间回放。四窗操作计数逐 key 求和；同一 (block_id,host_name) 合成一个文件。原始计数包括 op_count 的展开次数。

保留全部 29,819 个 key，555,643 次来源操作。文件为原模型对齐后的容量替身，总188.279296875 GiB；最热 key 有377,057次操作，占67.859579%。它独立成桶，不与尾部文件平均。源写全部转换为读，源偏移和因果顺序不保留。

为保留完整原生频率，不继续使用128GiB子集；与另外四项合计658.1700439453125 GiB，仍满足500–700GiB。容量不含副本、元数据及其他旧数据。实际准备前重新检查空间，不删除旧数据。

## 分桶与误差

按文件大小分组、原生访问计数降序排列，以L1误差降低量分裂为255桶/255测量FWD（准备每批20）。每桶FWD skew等于所含key的原生操作质量，桶内均匀选文件。模型理论文件请求概率TV约0.098570%，不是预测误差或实测概率误差。

冻结资料保存旧桶/窗口请求大小直方图，而非每key完整直方图。本模型先合并时间窗，再按旧桶内成员操作质量分摊到新桶。全体请求大小直方图守恒；单key请求大小相关性为近似，不能声称完整trace replay。请求大小仍4KiB对齐且不超过对应文件大小。

无stopafter时一次文件选择可能产生多个I/O；skew是操作请求目标而不是严格的文件打开次数配比。短时实测还受文件驻留和存储性能影响。静态模型不保留原热点的出现、退出和冷却时间，只表示全时段的频率快照。

## 配置及离线命令

配置：`bigdata_baleen_v2/rendered/run_baseline.vdb`。
本目录 baseline 指原生频率，不是均匀分布。旧四窗及Zipf目录保留，不被此入口覆盖。

```bash
cd /home/chris/ceph-test
python3 -m workload_common.single_v2 render --case baleen --design static_native \
  --output-root /home/chris/ceph-test/SINGLE_workload/baleen_static \
  --data-root /mnt/cephfs/single_baleen_static_v1 --rate max
python3 -m workload_common.single_v2 validate --case baleen \
  --output-root /home/chris/ceph-test/SINGLE_workload/baleen_static
```

数据配置路径 `/mnt/cephfs/single_baleen_static_v1/bigdata_baleen_v2`，本次未创建、未造数。新分桶不能复用旧READY；不要将该配置指向旧布局。

此目录只包含Baleen；CLI与实验矩阵使用时必须选择Baleen及本配置根，并选择baseline。现有五项矩阵的 business_phase 根不会自动替换为此目录，不能对本目录直接使用 --case all。

真实prepare/run仍需用户授权。运行使用 `/home/chris/ceph-tool/runtime/vdbench-fractional-xfer-v1`，支持小数请求大小直方图。原jar的 -s 仅证明参数解析，不代表该runtime已真实运行验证。
