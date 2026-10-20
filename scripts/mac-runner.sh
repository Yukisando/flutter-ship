#!/usr/bin/env bash
# Turns this Mac into the iOS build machine for flutter-ship apps: a self-hosted GitHub
# Actions runner, so `fastlane ios release` from Windows builds here instead of on GitHub's
# billed macOS runners.
#
#   bash mac-runner.sh tools                     # once: Homebrew tools, Xcode checks
#   bash mac-runner.sh add OWNER/REPO            # once per app repo: runner + IOS_RUNNER variable
#   bash mac-runner.sh status                    # what is installed and running
#   bash mac-runner.sh remove OWNER/REPO         # unregister that repo's runner
#   bash mac-runner.sh github OWNER/REPO         # send that repo back to GitHub's runners
#
# A personal GitHub account cannot share one runner between repos, so each repo gets its own
# runner under ~/actions-runners/<repo>. They are idle processes: no cost until a job comes.
# Builds run as you, in your login session (the signing keychain needs it), so stay logged in.
set -euo pipefail

RUNNERS="$HOME/actions-runners"
LABELS="flutter-ship"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

brew_env() {
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
}

ruby_path() {
  local prefix
  prefix="$(brew --prefix ruby@3.3)"
  echo "$prefix/bin:$(gem_bin)"
}

gem_bin() {
  "$(brew --prefix ruby@3.3)/bin/ruby" -e 'print Gem.bindir'
}

cmd_tools() {
  [ "$(uname)" = Darwin ] || die "run this on the Mac"

  say "Xcode"
  if ! xcode-select -p 2>/dev/null | grep -q '/Applications/Xcode'; then
    cat <<'TXT'
Full Xcode is not selected. Install Xcode from the App Store (the current version: App Store
Connect only takes builds from it), open it once, then run:
  sudo xcode-select -s /Applications/Xcode.app
  sudo xcodebuild -license accept
  xcodebuild -runFirstLaunch
and run `bash mac-runner.sh tools` again.
TXT
    exit 1
  fi
  xcodebuild -version

  say "Homebrew"
  brew_env
  if ! command -v brew >/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew_env
  fi

  say "Ruby 3.3, GitHub CLI, CocoaPods, jq (flutter-action needs it)"
  brew install ruby@3.3 gh cocoapods jq
  PATH="$(ruby_path):$PATH"
  gem install bundler --no-document

  say "GitHub login"
  gh auth status >/dev/null 2>&1 || gh auth login --hostname github.com --git-protocol https --web
  gh auth status

  say "Sleep"
  echo "A sleeping Mac takes no jobs. Never sleep on the charger (display may still turn off):"
  sudo pmset -c sleep 0 disksleep 0
  pmset -g | grep -E '^ *(sleep|disksleep|displaysleep)'

  say "Done. Next: bash mac-runner.sh add OWNER/REPO"
}

runner_version() {
  gh api repos/actions/runner/releases/latest --jq .tag_name | sed 's/^v//'
}

cmd_add() {
  local repo="${1:?usage: mac-runner.sh add OWNER/REPO}"
  local name="${repo#*/}"
  local dir="$RUNNERS/$name"
  brew_env
  command -v gh >/dev/null || die "run 'bash mac-runner.sh tools' first"

  if [ ! -x "$dir/run.sh" ]; then
    say "Runner for $repo in $dir"
    local arch ver
    case "$(uname -m)" in arm64) arch=arm64 ;; *) arch=x64 ;; esac
    ver="$(runner_version)"
    mkdir -p "$dir"
    curl -fsSL "https://github.com/actions/runner/releases/download/v$ver/actions-runner-osx-$arch-$ver.tar.gz" \
      | tar xz -C "$dir"
  fi

  say "Register with GitHub"
  local token
  token="$(gh api -X POST "repos/$repo/actions/runners/registration-token" --jq .token)"
  (
    cd "$dir"
    # The service keeps the PATH captured here (.path): Homebrew, Ruby 3.3, its gem bin.
    export PATH="$(ruby_path):$(brew --prefix)/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 # CocoaPods refuses to run without UTF-8
    ./config.sh --unattended --replace --url "https://github.com/$repo" --token "$token" \
      --name "$(scutil --get LocalHostName)-$name" --labels "$LABELS" --work _work
    ./svc.sh install >/dev/null 2>&1 || true
    ./svc.sh start
    ./svc.sh status | tail -3
  )

  say "Send $repo's iOS builds to this Mac"
  gh variable set IOS_RUNNER -R "$repo" --body '["self-hosted","macOS","flutter-ship"]'
  echo "IOS_RUNNER = $(gh variable get IOS_RUNNER -R "$repo")"
  echo "Done. 'fastlane ios release' for $repo now builds on this Mac."
}

cmd_github() {
  local repo="${1:?usage: mac-runner.sh github OWNER/REPO}"
  brew_env
  gh variable delete IOS_RUNNER -R "$repo"
  echo "$repo builds on GitHub's macos-26 runners again (billed minutes)."
}

cmd_remove() {
  local repo="${1:?usage: mac-runner.sh remove OWNER/REPO}"
  local dir="$RUNNERS/${repo#*/}"
  brew_env
  [ -d "$dir" ] || die "no runner in $dir"
  gh variable delete IOS_RUNNER -R "$repo" 2>/dev/null || true
  local token
  token="$(gh api -X POST "repos/$repo/actions/runners/remove-token" --jq .token)"
  (cd "$dir" && ./svc.sh stop || true; ./svc.sh uninstall || true; ./config.sh remove --token "$token")
  rm -rf "$dir"
  echo "Removed. $repo builds on GitHub's runners again."
}

cmd_status() {
  brew_env
  xcodebuild -version 2>/dev/null | head -1 || echo "Xcode: not selected"
  for t in brew gh pod; do printf '%-6s %s\n' "$t" "$(command -v $t || echo missing)"; done
  [ -d "$RUNNERS" ] || { echo "No runners yet."; return; }
  for dir in "$RUNNERS"/*/; do
    [ -x "$dir/svc.sh" ] || continue
    printf '\n%s\n' "$dir"
    (cd "$dir" && ./svc.sh status | grep -E 'Started|Stopped|not installed' || true)
  done
}

case "${1:-}" in
  tools) cmd_tools ;;
  add) cmd_add "${2:-}" ;;
  remove) cmd_remove "${2:-}" ;;
  github) cmd_github "${2:-}" ;;
  status) cmd_status ;;
  *) sed -n '2,13p' "$0"; exit 1 ;;
esac
