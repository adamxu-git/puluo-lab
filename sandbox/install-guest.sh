#!/bin/bash
# Run as root during trusted Ubuntu provisioning.
set -euo pipefail

if [[ $(id -u) != 0 || $(uname -m) != aarch64 ]]; then
  printf 'Run as root inside the ARM64 Ubuntu VM.\n' >&2
  exit 1
fi

install -d -m 755 /opt/puluo/node /opt/puluo/runtime /opt/puluo/browser /opt/puluo/browser-tools
install -d -m 700 -o experiment -g experiment /home/experiment/workspace
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

export DEBIAN_FRONTEND=noninteractive
export PATH=/opt/puluo/node/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PLAYWRIGHT_BROWSERS_PATH=/opt/puluo/browser
locks=$(cd -- "$(dirname -- "$0")" && pwd)/npm-locks

install_npm() {
  local directory=$1
  local package=$2
  export npm_config_cache="$scratch/npm-cache"
  if [[ -f "$locks/$directory/package-lock.json" ]]; then
    install -m 644 "$locks/$directory/package.json" "$locks/$directory/package-lock.json" "/opt/puluo/$directory/"
    npm ci --prefix "/opt/puluo/$directory" --no-fund --no-audit
  else
    npm install --prefix "/opt/puluo/$directory" --no-fund --no-audit --save-exact "$package"
  fi
}

stage=${1:-all}
case "$stage" in
  packages|runtime|browser|all) ;;
  *) printf 'Usage: install-guest.sh [packages|runtime|browser|all]\n' >&2; exit 2 ;;
esac

if [[ $stage == packages || $stage == all ]]; then
  apt-get update -q
  apt-get install -qy --no-install-recommends ca-certificates curl xz-utils bubblewrap
fi
if [[ $stage == packages ]]; then
  exit
fi

if [[ $stage != browser ]]; then
  node_archive=node-v24.22.1-linux-arm64.tar.xz
  curl -fsSL --retry 3 -o "$scratch/$node_archive" "https://nodejs.org/dist/v24.22.1/$node_archive"
  (
    cd "$scratch"
    printf '%s  %s\n' dbabf7a1cbf947e6059ffad2c27b80041db97dea1e553b62afdee7f13fca336e "$node_archive" | sha256sum -c -
  )
  tar -xJf "$scratch/$node_archive" --strip-components=1 -C /opt/puluo/node
  install_npm runtime @deepseek-ai/dsh@0.2.2-rc.1
  cd /home/experiment/workspace
  runuser -u experiment -- env PATH="$PATH" /opt/puluo/runtime/node_modules/.bin/dsh --version
  runuser -u experiment -- env PATH="$PATH" /opt/puluo/runtime/node_modules/.bin/dsh headless --help
fi

if [[ $stage == runtime ]]; then
  exit
fi
install_npm browser-tools @playwright/mcp@0.0.85
/opt/puluo/browser-tools/node_modules/.bin/playwright install --with-deps chromium
cd /home/experiment/workspace
runuser -u experiment -- env PATH="$PATH" PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_BROWSERS_PATH" node <<'JS'
const { chromium } = require('/opt/puluo/browser-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent('<title>Puluo offline test</title><button>Ready</button>');
    await page.getByRole('button', { name: 'Ready' }).click();
    if (await page.title() !== 'Puluo offline test') throw new Error('Browser smoke test failed');
    console.log('Chromium smoke test passed');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
JS
