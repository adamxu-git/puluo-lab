# 部署与运行指南

[返回项目首页](../README.zh-CN.md) · [English](guide.md)

## 运行要求

- 运行 macOS 26 或更新版本的 Apple Silicon Mac，已安装 macOS 命令行工具。
- 本机管理员权限，用于首次安装 Softnet。安装过程会调整 macOS 虚拟网络的 DHCP 租期。
- 实例专用的 DeepSeek API Key。Golden Image 已预装 DeepSeek Harness（DSH）0.2.2-rc.1、Playwright Chromium、定时器和串口审计工具，工作区和会话历史为空。
- 本机构建 Golden Image 时，确保 `qemu-img` 在 PATH 上。

以下命令均从仓库根目录执行。需要下载源码时，请克隆 [GitHub 仓库](https://github.com/adamxu-git/puluo-lab-homeforai)。

## 构建 Golden Image

构建脚本会校验锁定版本的 Canonical 云镜像，将 QCOW2 转成原始磁盘，然后用只读安装介质启动独立的构建 VM。该 VM 从允许的来源下载依赖，通过构建检查后自动关机。

```sh
./sandbox/bootstrap-mac
./sandbox/golden-image fetch-base
./sandbox/golden-image prepare sandbox/image-build/ubuntu-base.raw
./sandbox/golden-image run
./sandbox/golden-image export
```

输出为 `sandbox/image-build/puluo-golden-arm64.tvm` 和同目录的 `SHA256SUMS`。构建日志位于 `sandbox/logs/golden-build.log`。Tart 的这份 ARM64 镜像面向 Apple Silicon。移植到 x86_64 需要重新构建镜像并配置宿主环境。

## 创建并配置实例

如果你已有 `puluo-golden-arm64.tvm` 和对应的 `SHA256SUMS`，先在镜像目录运行 `shasum -a 256 -c SHA256SUMS`。

**终端 1。** 选择一个未使用的实例名。把示例中的镜像路径换成实际路径。若使用本机构建到 `sandbox/image-build/` 的镜像，可省略路径参数。

```sh
./sandbox/bootstrap-mac
./sandbox/new-instance lab-01 /absolute/path/to/puluo-golden-arm64.tvm
export PULUO_VM_NAME=lab-01
./sandbox/vm provision
```

**终端 2。** 配置正在运行的实例。需要自定义实验时，请先编辑两个示例提示词再复制到 VM。输入的 API Key 不回显，写入 VM 内仅 root 可读的文件。

```sh
export PULUO_VM_NAME=lab-01
./sandbox/guest-admin 'cloud-init status --wait'
./sandbox/deepseek-key
./sandbox/background/install
./sandbox/guest-admin 'sudo install -m 644 /dev/stdin /etc/systemd/system/puluo-wake.service' < sandbox/puluo-wake.service
./sandbox/guest-admin 'sudo systemctl daemon-reload'
./sandbox/guest-admin 'sudo install -m 644 /dev/stdin /etc/puluo/system-prompt.yml' < sandbox/system-prompt.example.yml
./sandbox/guest-admin 'sudo install -m 644 /dev/stdin /etc/puluo/wake.txt' < sandbox/wake.example.txt
./sandbox/guest-admin 'sudo systemctl enable puluo-wake.timer'
./sandbox/dashboard/record-timer
```

默认配置下，Chromium 可访问 VM 内的本地网页。需要通过 VM 内代理访问公网 IPv4 的 HTTP 和 HTTPS 页面时，趁实例仍在管理模式下运行 `./sandbox/browser-network/install`。

在终端 2 关机，等终端 1 的 `vm provision` 退出，再在终端 1 启动隔离模式。

```sh
./sandbox/guest-admin 'sudo systemctl poweroff'
```

```sh
./sandbox/vm isolated
```

## 查看和管理运行

定时器在 Ubuntu 启动时加载。每次唤醒时，DSH 会加载系统提示词，把唤醒词作为新消息发送至已有会话，并自动压缩会话历史。关机期间错过的时段会跳过。让 macOS 开机时自动启动 VM 需要另行配置。

```sh
PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard
```

打开[本地看板](http://127.0.0.1:8765)查看 Tart 状态、宿主磁盘占用和串口审计记录。展开某一轮即可查看已记录的工具动作和 Token 用量。定时器面板显示最近一次核验状态，并按默认日程计算下一时段。修改过日程时，可在管理模式用 `systemctl list-timers puluo-wake.timer` 查实际触发时间。

| 操作 | 命令 |
| --- | --- |
| 跟踪串口日志 | `PULUO_VM_NAME=lab-01 ./sandbox/vm observe` |
| 更改看板端口 | `PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard --port 8766` |
| 在管理模式刷新定时器状态快照 | `PULUO_VM_NAME=lab-01 ./sandbox/dashboard/record-timer` |
| 列出本地 VM | `./sandbox/vm list` |
| 停止指定实例 | `PULUO_VM_NAME=lab-01 ./sandbox/vm stop` |

命名实例的串口记录位于 `sandbox/instances/<实例名>/logs/`。日志在 32 MiB 时轮转，保留上一份文件，记录 DSH 事件及 VM 串口输出。

## 网络模式

| 模式 | 宿主机和 VM 的网络行为 |
| --- | --- |
| `provision` | 允许 Mac 发起管理 SSH，允许 VM 向配置的管理白名单目标发起 HTTPS 连接 |
| `isolated` | 关闭管理 SSH。默认出站 IPv4 白名单覆盖 DeepSeek API。可选的公网浏览经 VM 内代理和防火墙控制。 |
| `offline` | VM 运行时无网络转发，宿主机仍可采集串口日志。 |

更换宿主、模型端点或网络策略后，请重新验证隔离边界。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| 管理 SSH 连不上 | 确认 VM 以 `provision` 模式运行，且两个终端使用同一个 `PULUO_VM_NAME`。首次启动时，SSH 需要一段时间就绪。 |
| 没出现运行记录 | 确认 VM 在计划时段内运行，再查看定时器和串口日志。唤醒服务需要 API Key 和两个提示词文件。 |
| 看板无法使用 8765 端口 | 用 `vm dashboard --port 8766` 改用其他端口，并在 `127.0.0.1` 打开对应端口。 |
| 镜像导出提示验证失败 | 先查看 `sandbox/logs/golden-build.log` 找到构建失败原因，再重试。 |
