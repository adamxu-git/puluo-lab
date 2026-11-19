# Contributing to Puluo Lab

[简体中文](#简体中文)

Use the [issue templates](https://github.com/adamxu-git/puluo-lab-homeforai/issues/new/choose) for bug reports and feature proposals. For bugs, include the repository revision, macOS version, VM mode, the command you ran, and a short redacted error excerpt. See the [security policy](SECURITY.md) for vulnerability reports.

## Check your changes

Install Git, Bash, Python 3.9+, and Node.js, then run this from the repository root.

```sh
python3 scripts/check.py
```

The same checks run on GitHub Actions. They parse the Bash, Python, JavaScript, and JSON source without starting a VM or calling DeepSeek. For changes to image building, networking, or scheduling, summarize any real-VM checks you ran on Apple Silicon in the pull request. Update both languages when you change a documented workflow.

Keep API keys, SSH keys, VM images, instance state, and raw audit logs out of issues and patches. Use synthetic data for examples and screenshots.

## 简体中文

通过 [Issue 模板](https://github.com/adamxu-git/puluo-lab-homeforai/issues/new/choose)报告问题或提出功能建议。报告故障时，请带上仓库版本、macOS 版本、VM 模式、执行命令和脱敏后的错误片段。安全问题请参阅[安全报告指引](SECURITY.md#简体中文)。

安装 Git、Bash、Python 3.9 或更新版本和 Node.js，然后在仓库根目录运行 `python3 scripts/check.py`。GitHub Actions 会执行同样的 Bash、Python、JavaScript 和 JSON 检查。这些检查无需启动 VM 或调用 DeepSeek。若修改镜像构建、网络或调度，在 PR 里说明你在 Apple Silicon 真机上做过的验证。操作流程有变化时，请同步修改中英文文档。

提交内容和 Issue 请排除 API Key、SSH 密钥、虚拟机镜像、实例状态和原始审计日志。示例和截图使用合成数据。
