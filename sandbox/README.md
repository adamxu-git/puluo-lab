# 沙盒组件

[部署与运行指南](../docs/guide.zh-CN.md) · [English setup guide](../docs/guide.md)

本目录包含宿主机上的 Tart 管理脚本，以及 Ubuntu VM 内的初始化、定时运行和网络配置。下表按用途列出入口，命令路径相对于本目录。

| 组件 | 入口 | 用途 |
| --- | --- | --- |
| 宿主工具 | [`./bootstrap-mac`](bootstrap-mac) | 安装 Tart 和 Softnet |
| Golden Image | [`./golden-image`](golden-image) | 下载基础镜像、运行构建 VM、导出并生成校验文件 |
| 实例管理 | [`./new-instance`](new-instance)、[`./vm`](vm) | 导入实例、选择网络模式、观察串口或停止 VM |
| 来宾配置 | [`./guest-admin`](guest-admin)、[`./deepseek-key`](deepseek-key) | 在管理模式下配置实例和 DeepSeek 凭据 |
| 定时运行 | [`puluo-wake.timer`](puluo-wake.timer)、[`guest-run.py`](guest-run.py) | 定时续接 DSH 会话，并将运行事件写到串口 |
| 后台任务 | [`./background/install`](background/install) | 安装后台任务 MCP 与 systemd 服务 |
| 公网浏览 | [`./browser-network/install`](browser-network/install) | 在管理模式配置可选的 Chromium 公网代理 |
| 宿主看板 | [`./vm dashboard`](vm)、[`./dashboard/record-timer`](dashboard/record-timer) | 从本机查看运行状态，在管理模式刷新定时器快照 |

后台任务工具可启动、检查或停止工作区里的 `.puluo-background.py`。同一时间最多运行一个任务，单次限时两小时，最多使用单核的 25%、256 MiB 内存和 32 个任务，网络仅可经 VM 的回环地址通信。

## 本地数据

- `tools/`、`downloads/`、`image-build/` 分别存放宿主工具、安装来源和镜像构建产物。
- `state/active-instance` 保存本机默认实例名。设置 `PULUO_VM_NAME` 可以覆盖默认值。
- `tart/vms/<实例名>/` 保存虚拟磁盘，`instances/<实例名>/state/` 保存该实例的管理状态。
- `instances/<实例名>/logs/` 保存宿主串口日志和看板的定时器快照。看板按 12 秒间隔刷新。
