# Puluo Lab

[简体中文](README.zh-CN.md)

Puluo Lab runs a scheduled AI experiment in an Ubuntu ARM64 VM on an Apple Silicon Mac. The Golden Image includes DeepSeek Harness (DSH) 0.2.2-rc.1, Playwright Chromium, the systemd timer, and serial audit collection. Each new instance gets its own management SSH key, machine identity, and DSH session. The image starts with an empty workspace and session history. Supply the DeepSeek API key when configuring an instance.

## Start an instance

If you already have a local `puluo-golden-arm64.tvm` and `SHA256SUMS`, run `shasum -a 256 -c SHA256SUMS` in their directory. You can also build the image locally using the steps below.

Run these commands from the repository root on an Apple Silicon Mac with the macOS command-line tools. The first Softnet installation requires administrator access and changes the DHCP lease time for the macOS virtual network.

```sh
./sandbox/bootstrap-mac
./sandbox/new-instance lab-01 /absolute/path/to/puluo-golden-arm64.tvm
export PULUO_VM_NAME=lab-01
./sandbox/vm provision
```

In another terminal, configure the instance from the repository root. Edit the example prompts to suit your experiment. The API key entry is hidden.

```sh
export PULUO_VM_NAME=lab-01
./sandbox/deepseek-key
./sandbox/guest-admin 'sudo install -m 644 /dev/stdin /etc/puluo/system-prompt.yml' < sandbox/system-prompt.example.yml
./sandbox/guest-admin 'sudo install -m 644 /dev/stdin /etc/puluo/wake.txt' < sandbox/wake.example.txt
./sandbox/guest-admin 'sudo systemctl enable puluo-wake.timer'
./sandbox/guest-admin 'sudo systemctl poweroff'
```

Wait for `vm provision` to exit after Ubuntu shuts down. Then start the instance in isolated mode.

```sh
./sandbox/vm isolated
```

The enabled timer starts when Ubuntu boots. It wakes the experiment at 23:00 Beijing time and again at 00:00, 01:00, 02:00, 03:00, and 04:00. Each run has a 10-minute timeout. The timer skips slots missed while the VM is off. Starting the VM automatically when macOS boots requires a separate host configuration.

The system prompt defines the long-term behavior. The wake prompt starts each turn. DSH resumes the same native session and automatically compacts its history.

Run `PULUO_VM_NAME=lab-01 ./sandbox/vm observe` to watch the host's serial log. The collector rotates the log at 32 MiB and retains one previous file. Isolated mode blocks inbound SSH and allows outbound HTTPS to the configured DeepSeek API addresses. Chromium can access pages inside the VM. Recheck the network boundary after changing the host, API endpoint, or network policy.

The image uses Tart's ARM64 format. For an x86_64 server, reuse the initialization, scheduling, and audit configuration when building an image for that architecture.

## Build the Golden Image

Put `qemu-img` on your PATH to convert Canonical's QCOW2 image to a raw disk. The builder boots a separate VM with read-only installation media and downloads the dependencies from allowlisted sources. The VM shuts down after the build checks pass.

```sh
./sandbox/bootstrap-mac
./sandbox/golden-image fetch-base
./sandbox/golden-image prepare sandbox/image-build/ubuntu-base.raw
./sandbox/golden-image run
./sandbox/golden-image export
```

The image and checksum appear in `sandbox/image-build/`. The build log is at `sandbox/logs/golden-build.log`.
