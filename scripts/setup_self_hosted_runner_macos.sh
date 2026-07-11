#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-TaterTotterson/Tater-Wake-Words}"
RUNNER_ROOT="${RUNNER_ROOT:-$HOME/actions-runners/tater-wake-words}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname -s)-tater-wake-words}"
RUNNER_LABELS="${RUNNER_LABELS:-tater-wake-words}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This runner setup is intended for macOS arm64."
  exit 1
fi

command -v gh >/dev/null 2>&1 || {
  echo "GitHub CLI is required. Install gh and run gh auth login first."
  exit 1
}

gh auth status >/dev/null

mkdir -p "$RUNNER_ROOT"
cd "$RUNNER_ROOT"

if [[ ! -x ./config.sh ]]; then
  release_tag="$(gh api repos/actions/runner/releases/latest --jq '.tag_name')"
  version="${release_tag#v}"
  asset_url="$(
    gh api "repos/actions/runner/releases/tags/${release_tag}" \
      --jq '.assets[] | select(.name | test("actions-runner-osx-arm64-.*\\.tar\\.gz$")) | .browser_download_url' \
      | head -n 1
  )"
  if [[ -z "$asset_url" ]]; then
    echo "Could not find a macOS arm64 Actions runner asset for ${release_tag}."
    exit 1
  fi
  archive="actions-runner-osx-arm64-${version}.tar.gz"
  curl -L "$asset_url" -o "$archive"
  tar xzf "$archive"
fi

token="$(gh api --method POST "repos/${REPO}/actions/runners/registration-token" --jq '.token')"

if [[ -f .runner ]]; then
  ./config.sh remove --token "$token" || true
fi

./config.sh \
  --url "https://github.com/${REPO}" \
  --token "$token" \
  --name "$RUNNER_NAME" \
  --labels "$RUNNER_LABELS" \
  --work "_work" \
  --unattended \
  --replace

if [[ -x ./svc.sh ]]; then
  ./svc.sh install
  ./svc.sh start
  ./svc.sh status || true
else
  echo "Runner configured. Start it with: cd '$RUNNER_ROOT' && ./run.sh"
fi
