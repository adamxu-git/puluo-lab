# 本地实验沙盒

Tart 使用本目录下的 `tart/` 作为独立数据目录。`tools/` 保存宿主工具，`downloads/` 保存安装镜像。`state/active-instance` 记录本机的默认实例，也可以用 `PULUO_VM_NAME` 指定实例。新实例的虚拟磁盘位于 `tart/vms/<实例名>/disk.img`，宿主侧记录位于 `instances/<实例名>/logs/`。

`./vm list` 查看项目中登记的 VM。`./vm offline` 以无网络转发模式启动指定 VM，并将串口持续写入实例日志目录中的 `serial.log`。另开终端运行 `./vm observe` 查看 Mac 上的串口日志，按 Ctrl+C 结束查看。查看过程只读取 Mac 文件，日志覆盖 DSH 导出的事件。`./vm stop` 停止 VM。`offline` 模式可附加一次性的 cloud-init 介质。

Ubuntu 24.04.5 ARM64 已从 Canonical 云镜像断网启动，宿主串口日志收到了 Ubuntu 登录提示。Softnet 管理员辅助程序已安装在 `/Library/PrivilegedHelperTools/puluo-search/softnet`。Softnet 启动时还把 macOS 虚拟网络 DHCP 租期设置为 600 秒。项目的 VM、工具、配置和日志仍存于此目录。

`./vm provision` 是管理模式，默认禁止双向通信，只允许 Mac 从虚拟网桥发起 SSH，以及 VM 向指定的公共 IPv4 地址发起 HTTPS。`./deepseek-key` 在管理模式下读取实验凭据，终端不回显，凭据存于 VM 内的 root 专用文件。`./vm isolated` 关闭管理 SSH，公共 HTTPS 目的地使用单独的白名单。正式实验的定时器在首次验收前保持停用。验收进度见上一级的 `TODO.md`。

ARM64 Ubuntu 中的 Playwright 已成功启动 headless Chromium 并点击本地测试页。Playwright MCP 也已通过 stdio 初始化并公布浏览器导航和点击工具。DeepSeek HTTPS 端点已连通，未传凭据时返回 HTTP 401。

在管理模式运行 `./background/install` 可给新实例装上后台任务工具。模型通过 DSH 的 background MCP 工具启动、检查或停止工作区里的 `.puluo-background.py`。同时最多运行一个，单次最多两小时，限制为单核的 25%、256 MiB 内存和 32 个进程或线程，网络仅可经 VM 回环地址通信。宿主串口日志会记录控制操作。网页搜索由 DSH 的 `web_search` 走 DeepSeek 服务端，受既有 API 白名单约束。

在管理模式运行 `./browser-network/install` 并切回隔离模式后，Chromium 可通过 VM 内代理打开公网 IPv4 的 HTTP 和 HTTPS 页面。代理与防火墙会拦截私网和宿主目标。代理监听 `127.0.0.2:3128`，后台任务的网络权限仍限于 `127.0.0.1`。浏览器访问 VM 自己的本地网页时绕过代理。

在本目录运行 `./vm dashboard`，浏览器打开 `http://127.0.0.1:8765`。看板在宿主读取 Tart 状态、磁盘数据和串口日志，每 12 秒刷新。切换正式实验和验收记录，展开每轮查看工具动作及用量。若在管理模式下调整定时器，运行 `./dashboard/record-timer` 更新状态核验时间。看板会标注核验时间和下一计划时段。按 Ctrl+C 结束看板。
