# GraphChi 来源与参数映射

## 主来源

- Kyrola、Blelloch、Guestrin，*GraphChi: Large-Scale Graph Computation on
  Just a PC*，OSDI 2012（CCF-A）。
- 论文页面：<https://www.usenix.org/conference/osdi12/technical-sessions/presentation/kyrola>
- PDF：<https://www.usenix.org/system/files/conference/osdi12/osdi12-final-126.pdf>

论文支持图被划分为shard、顶点interval按顺序处理，以及PSW通过memory shard
和sliding window执行图计算。论文没有规定本负载使用的4 shard、等容量shard、
100 rank、Zipf(0.99)或150秒阶段。

## 当前映射

当前版本有意删除PSW window层，只保留下列映射：

1. `shard_00`到`shard_03`表示四个按目标顶点范围划分的数据分区；
2. 四阶段顺序处理四个shard，表达GraphChi的interval/shard扫描生命周期；
3. 每个shard内部独立使用100个Zipf rank，制造可验证的阶段内文件冷热；
4. shard热点在150秒阶段边界直接切换，不设论文未规定的中间比例。

因此本负载应称为“GraphChi shard生命周期启发的冷热识别负载”，不能称为
GraphChi PSW复现或完整GraphChi benchmark。

## Zipf与执行工具

- YCSB/SoCC 2010提供常用Zipfian popularity模型：
  <https://doi.org/10.1145/1807128.1807152>
- Oracle Vdbench：
  <https://www.oracle.com/downloads/server-storage/vdbench-downloads.html>

每个shard的每个固定文件大小档独立计算Zipf(0.99)，再聚合到100个等容量rank。
Vdbench只负责把FSD/FWD/RD模型施加到CephFS。

## 不允许的结论

- 不得把shard等容量或Zipf解释为GraphChi论文测量值；
- 不得声称当前模型实现了memory shard或sliding window读取；
- 不得将其解释为真实生产图的边分布；
- 不评价GraphChi计算性能、PageRank吞吐或收敛速度。
