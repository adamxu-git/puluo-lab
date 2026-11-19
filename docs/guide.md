# Setup and operations

[Back to Puluo Lab](../README.md) · [简体中文](guide.zh-CN.md)

## Requirements

- An Apple Silicon Mac running macOS 26 or later, with the macOS Command Line Tools.
- A local administrator for the first Softnet installation, which adjusts the host virtual network's DHCP lease time.
- A DeepSeek API key for the instance. The Golden Image contains DeepSeek Harness (DSH) 0.2.2-rc.1, Playwright Chromium, scheduling, and serial audit collection. Its workspace and session history start empty.
- `qemu-img` on your PATH if you’re building the Golden Image.

Run the commands in this guide from the repository root. If you need a checkout, clone [the GitHub repository](https://github.com/adamxu-git/puluo-lab-homeforai).

## Build the Golden Image

The builder verifies the pinned Canonical cloud image checksum, converts the QCOW2 image to a raw disk, and boots a separate VM with read-only installation media. That VM downloads dependencies from allowlisted sources and powers off after its build checks pass.

```sh
./sandbox/bootstrap-mac
./sandbox/golden-image fetch-base
./sandbox/golden-image prepare sandbox/image-build/ubuntu-base.raw
./sandbox/golden-image run
./sandbox/golden-image export
```

The export produces `sandbox/image-build/puluo-golden-arm64.tvm` and `sandbox/image-build/SHA256SUMS`. Build output goes to `sandbox/logs/golden-build.log`. Tart’s ARM64 image targets Apple Silicon. An x86_64 port would require a new image and host setup.

## Create and provision an instance

If you received a prebuilt `puluo-golden-arm64.tvm` and its `SHA256SUMS`, verify the download with `shasum -a 256 -c SHA256SUMS` in their directory.

**Terminal 1.** Choose an unused instance name. Replace the image path below with yours, or omit it to use the locally built image in `sandbox/image-build/`.

```sh
./sandbox/bootstrap-mac
./sandbox/new-instance lab-01 /absolute/path/to/puluo-golden-arm64.tvm
export PULUO_VM_NAME=lab-01
./sandbox/vm provision
```

**Terminal 2.** Configure the running instance. Edit the example prompt files before copying them to the guest if you want to customize your experiment. The API key prompt hides input and stores the key in a root-only file inside the VM.

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

If you want Chromium to reach public IPv4 HTTP and HTTPS sites via the guest proxy, run `./sandbox/browser-network/install` while still in management mode. The default configuration lets Chromium access local pages inside the guest.

Power off from Terminal 2 and wait until `vm provision` returns in Terminal 1. Then launch isolated mode in Terminal 1.

```sh
./sandbox/guest-admin 'sudo systemctl poweroff'
```

```sh
./sandbox/vm isolated
```

## Observe and manage runs

The timer starts when Ubuntu boots. At each scheduled time, DSH loads the system prompt and sends the wake prompt as a new user message in the saved session. DSH automatically compacts its session history. The timer skips slots missed during downtime. macOS startup of the VM requires separate host configuration.

```sh
PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard
```

Open [the local dashboard](http://127.0.0.1:8765). It reads Tart status, host disk usage, and the serial audit log. Expand a run to review its recorded tool events and token usage. The timer panel shows the last observed state and the next slot calculated from the default schedule. If you modify the schedule, read the live timer from management mode with `systemctl list-timers puluo-wake.timer`.

| Task | Command |
| --- | --- |
| Follow the serial log | `PULUO_VM_NAME=lab-01 ./sandbox/vm observe` |
| Use a different dashboard port | `PULUO_VM_NAME=lab-01 ./sandbox/vm dashboard --port 8766` |
| Refresh the timer snapshot in management mode | `PULUO_VM_NAME=lab-01 ./sandbox/dashboard/record-timer` |
| List local VMs | `./sandbox/vm list` |
| Stop the instance | `PULUO_VM_NAME=lab-01 ./sandbox/vm stop` |

Serial output for a named instance is stored under `sandbox/instances/<name>/logs/`. The collector rotates the log at 32 MiB and keeps one previous file. It captures the events emitted by DSH and the guest serial console.

## Network modes

| Mode | Host and guest connectivity |
| --- | --- |
| `provision` | Management SSH from the Mac and guest HTTPS to the configured provisioning allowlist |
| `isolated` | Management SSH is closed. The default outbound IPv4 allowlist covers the DeepSeek API. Optional public browsing uses the guest proxy and firewall. |
| `offline` | VM runs without network forwarding. Host serial capture remains available. |

Recheck the network boundary after changing the host, model endpoint, or network policy.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Management SSH cannot connect | Confirm the VM is running in `provision` and both terminals use the same `PULUO_VM_NAME`. First boot can take a moment to start SSH. |
| No run has appeared | Check that the VM was running at a scheduled slot, then check timer state and the serial log. The wake service requires the key and both prompt files. |
| Dashboard cannot start on 8765 | Try another port with `vm dashboard --port 8766` and open that port on `127.0.0.1`. |
| Image export says verification failed | Inspect `sandbox/logs/golden-build.log` for the build failure before retrying. |
