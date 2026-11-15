#!/bin/bash
set -euo pipefail

seed=$1
cd "$seed"

# Match the installer network policy. Use the ordinary hosts file on clones.
cp /etc/hosts /run/puluo-original-hosts
cat provision-hosts >> /etc/hosts
sed -i 's|http://ports.ubuntu.com|https://ports.ubuntu.com|g' /etc/apt/sources.list.d/ubuntu.sources
export DEBIAN_FRONTEND=noninteractive
export PATH=/opt/puluo/node/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PLAYWRIGHT_BROWSERS_PATH=/opt/puluo/browser
install -d -m 755 /opt/puluo /etc/puluo
if [[ -f software.tgz ]]; then
  sha256sum -c software.sha256
  apt-get update -q
  apt-get install -qy --no-install-recommends ca-certificates curl xz-utils bubblewrap
  tar -xzf software.tgz -C /opt/puluo
  /opt/puluo/browser-tools/node_modules/.bin/playwright install-deps chromium
else
  /bin/bash "$seed/install-guest.sh" all
fi
install -d -o experiment -g experiment -m 700 /home/experiment/workspace /home/experiment/acceptance
install -m 755 guest-run.py /opt/puluo/guest-run.py
install -m 644 cordis.yml /etc/puluo/guest.cordis.yml
install -m 644 puluo-wake.service puluo-wake.timer /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/puluo-wake.service /etc/systemd/system/puluo-wake.timer
systemctl mask serial-getty@hvc0.service

cd /home/experiment/workspace
runuser -u experiment -- env PATH="$PATH" /opt/puluo/runtime/node_modules/.bin/dsh --version
runuser -u experiment -- env PATH="$PATH" PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_BROWSERS_PATH" node <<'JS'
const { chromium } = require('/opt/puluo/browser-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent('<button>Image build test</button>');
    await page.getByRole('button').click();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
JS

test ! -e /etc/puluo/deepseek-key
test ! -e /var/lib/puluo
test ! -e /home/experiment/.dsh-puluo
test ! -e /home/experiment/.dsh-acceptance
test ! -e /home/setup
test -z "$(find /etc/ssh -maxdepth 1 -name 'ssh_host_*' -print -quit)"
test "$(systemctl is-enabled puluo-wake.timer || true)" = disabled
cat /run/puluo-original-hosts > /etc/hosts
apt-get clean
cloud-init clean --logs --machine-id --seed
sync
printf '\nPULUO_GOLDEN_IMAGE_READY\n' > /dev/hvc0
systemctl --no-block poweroff
