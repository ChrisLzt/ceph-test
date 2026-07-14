# 来源与映射

## 应用语义

- NSF NCAR/MMM WRF模型：<https://www.mmm.ucar.edu/models/wrf>
- WRF运行涉及输入/边界状态、restart/checkpoint和history/output文件。

本负载将其映射为：

| WRF语义 | 数据组 | 正式访问 |
|---|---|---|
| 输入和边界状态 | `startup/wrf_state` | 启动读 |
| restart/checkpoint | `checkpoint/wrfrst_current` | 首次读和复热读 |
| history/output | `history/wrfout_current` | history读 |

## 执行工具

- IOR官方仓库：<https://github.com/hpc/ior>
- IOR官方文档：<https://ior.readthedocs.io/>

本负载使用IOR的MPI并行、POSIX、file-per-process、Direct I/O以及block/transfer
size控制能力。

## 来源边界

WRF和IOR来源支持上述文件生命周期与并行I/O方法。三组等容量、750GiB、4个
rank、每阶段150秒和checkpoint复热是冷热识别实验设计，不是WRF trace给出的
容量或访问比例。因此本负载不能称为完整WRF benchmark。
