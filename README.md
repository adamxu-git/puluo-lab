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

Wait for `vm provision` to exit after Ubuntu shuts down. Then start the instance in isolated mode.

```sh
./sandbox/vm isolated
```

The enabled timer starts when Ubuntu boots. It wakes the experiment at 23:00 Beijing time and again at 00:00, 01:00, 02:00, 03:00, and 04:00. systemd terminates each run at 30 minutes. The timer skips slots missed while the VM is off. Starting the VM automatically when macOS boots requires a separate host configuration.

DSH loads the system prompt on each wake and submits the wake prompt as a fresh user message in the existing session. Both example files use the same sentence. DSH automatically compacts its history.

Run `PULUO_VM_NAME=lab-01 ./sandbox/vm observe` to watch the host's serial log. The collector rotates the log at 32 MiB and retains one previous file. Isolated mode blocks inbound SSH. Chromium can access pages inside the VM. To enable public browsing, run `./sandbox/browser-network/install` in the management session before powering off. Chromium then uses a guest proxy for public IPv4 HTTP and HTTPS. Ordinary guest processes can connect directly to the configured DeepSeek API. Recheck the network boundary after changing the host, API endpoint, or network policy.

For a local dashboard, run `PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard` and open [localhost:8765](http://127.0.0.1:8765). It reads the instance's serial audit log and shows the VM status and recorded runs. After changing the timer in management mode, run `./sandbox/dashboard/record-timer` with the same instance name to refresh the displayed timer status.

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
