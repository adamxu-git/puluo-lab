# Puluo Lab

[English](README.md)

本项目提供一个在 Apple Silicon Mac 上运行的 Ubuntu ARM64 自主 AI 实验环境。Golden Image 包含 DeepSeek Harness 0.2.2-rc.1、Playwright Chromium、定时器和串口审计代码。每台新实例独立生成 SSH 管理密钥、机器身份和会话。发布镜像里没有 API Key、聊天历史或项目工作文件。

## 从 Golden Image 创建实例

已有本地 `puluo-golden-arm64.tvm` 和 `SHA256SUMS` 时，在镜像目录运行 `shasum -a 256 -c SHA256SUMS`。公开仓库提供构建脚本和依赖锁文件，构建时从 Canonical 和各软件项目的官方源下载。

在仓库根目录运行以下命令。需要 Apple Silicon Mac、macOS 命令行工具和本机管理员账户。首次安装 Softnet 会请求管理员授权，组件会调整 macOS 虚拟网络的 DHCP 租期。

```sh
./sandbox/bootstrap-mac
./sandbox/new-instance lab-01 /absolute/path/to/puluo-golden-arm64.tvm
export PULUO_VM_NAME=lab-01
./sandbox/vm provision
```

在另一个终端从仓库根目录运行以下命令。输入的 Key 不回显。

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
./sandbox/guest-admin 'sudo systemctl poweroff'
```

等第一个终端里的 `vm provision` 退出，确认 VM 已关机，再启动隔离模式。

```sh
./sandbox/vm isolated
```

每次唤醒都会加载系统提示词，并在同一个 DSH 会话里新发一条唤醒消息。两个示例文件使用同一句话。DSH 负责自动压缩历史。定时器按北京时间在 23:00 及次日 00:00、01:00、02:00、03:00、04:00 各触发一次。每轮到了 30 分钟由 systemd 终止，关机漏掉的时间点不补跑。启用定时器后，它会在 Ubuntu 启动时加载。macOS 开机启动 VM 需要另外配置。

运行 `PULUO_VM_NAME=lab-01 ./sandbox/vm observe` 查看 Mac 上的串口审计日志。采集到 32 MiB 时轮转，保留上一份文件。实验模式关闭管理 SSH。浏览器可访问 VM 内部网页。若要开放公网浏览，在管理模式下关机前运行 `./sandbox/browser-network/install`。Chromium 会通过 VM 内的代理访问公网 IPv4 的 HTTP 和 HTTPS 页面，普通进程直连公网仍限于 DeepSeek API。更换主机、模型端点或网络策略后，应重新验证隔离。

运行 `PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard`，在浏览器打开本地看板。它从 Mac 读取该实例的串口日志，显示 VM 状态和已记录的运行。管理模式下修改定时器之后，用同一个实例名运行 `./sandbox/dashboard/record-timer` 刷新定时器状态。[打开本地看板](http://127.0.0.1:8765)

本镜像使用 Tart 的 ARM64 虚拟机格式。换用 x86_64 服务器时，可复用云镜像初始化、DSH 调度和审计设计，并为新架构重新构建。

## 在本机重新生成 Golden Image

需要 `qemu-img` 在 PATH 上，用于把 Canonical 的 QCOW2 转成 Tart 支持的磁盘。构建过程使用独立的空白虚拟机、初始无账号凭据的只读安装介质，以及 Softnet 允许的安装源。构建验证成功后，虚拟机会自动关机。

```sh
./sandbox/bootstrap-mac
./sandbox/golden-image fetch-base
./sandbox/golden-image prepare sandbox/image-build/ubuntu-base.raw
./sandbox/golden-image run
./sandbox/golden-image export
```

输出在 `sandbox/image-build/puluo-golden-arm64.tvm`，同目录生成校验文件。构建日志在 `sandbox/logs/golden-build.log`。
