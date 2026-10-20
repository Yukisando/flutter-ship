#!/usr/bin/env bash
# Turns this Mac into the iOS build machine for flutter-ship apps: a self-hosted GitHub
# Actions runner, so `fastlane ios release` from Windows builds here instead of on GitHub's
# billed macOS runners.
#
#   bash mac-runner.sh tools                     # once: Homebrew tools, Xcode checks
#   bash mac-runner.sh add OWNER/REPO [...]      # once per app repo: runner + IOS_RUNNER variable
#   bash mac-runner.sh add-all OWNER             # every OWNER repo with fastlane/ship.yml and an iOS workflow
#   bash mac-runner.sh status                    # each runner: service, process, GitHub (online, busy)
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
  curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p' | head -1
}

# RUNNER_TOKEN (a registration or remove token made elsewhere, e.g. by flutter-ship on Windows)
# wins; otherwise this Mac's own gh login asks GitHub for one.
runner_token() {
  local repo="$1" kind="$2"
  if [ -n "${RUNNER_TOKEN:-}" ]; then echo "$RUNNER_TOKEN"; return; fi
  command -v gh >/dev/null || die "no RUNNER_TOKEN and no gh: run 'bash mac-runner.sh tools' first"
  gh api -X POST "repos/$repo/actions/runners/$kind-token" --jq .token
}

# The IOS_RUNNER variable needs this Mac's gh login; flutter-ship sets it itself before each build.
set_variable() {
  local repo="$1"
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    gh variable set IOS_RUNNER -R "$repo" --body '["self-hosted","macOS","flutter-ship"]'
    echo "IOS_RUNNER = $(gh variable get IOS_RUNNER -R "$repo")"
  else
    echo "IOS_RUNNER not set from here (no gh login): flutter-ship sets it before each iOS build."
  fi
}

cmd_add() {
  local repo="${1:?usage: mac-runner.sh add OWNER/REPO}"
  local name="${repo#*/}"
  local dir="$RUNNERS/$name"
  brew_env
  command -v brew >/dev/null || die "run 'bash mac-runner.sh tools' first"

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
  token="$(runner_token "$repo" registration)"
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
  set_variable "$repo"
  echo "Done. 'fastlane ios release' for $repo now builds on this Mac."
}

# Every repo of OWNER that ships with flutter-ship and builds iOS in a workflow.
cmd_add_all() {
  local owner="${1:?usage: mac-runner.sh add-all OWNER}"
  brew_env
  local repos=() r
  for r in $(gh repo list "$owner" --limit 200 --no-archived --json nameWithOwner --jq '.[].nameWithOwner'); do
    gh api "repos/$r/contents/fastlane/ship.yml" --silent 2>/dev/null || continue
    gh api "repos/$r/contents/.github/workflows/ios-release.yml" --silent 2>/dev/null || continue
    repos+=("$r")
  done
  [ ${#repos[@]} -gt 0 ] || die "no flutter-ship repo with an iOS workflow under $owner"
  say "flutter-ship repos with an iOS workflow: ${repos[*]}"
  for r in "${repos[@]}"; do
    if ! gh api "repos/$r/contents/.github/workflows/ios-release.yml" --jq .content | base64 -d | grep -q IOS_RUNNER; then
      echo "SKIP $r: its ios-release.yml ignores IOS_RUNNER (copy flutter-ship's template first)"
      continue
    fi
    cmd_add "$r"
  done
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
  token="$(runner_token "$repo" remove)"
  (cd "$dir" && ./svc.sh stop || true; ./svc.sh uninstall || true; ./config.sh remove --token "$token")
  rm -rf "$dir"
  echo "Removed. $repo builds on GitHub's runners again."
}

# One runner's state, in words: the launchd service, the process, and what GitHub sees.
# svc.sh's own status only greps `launchctl list`, which never says "running", lists a
# loaded job whose process died under "Started:", and misses a runner started by ./run.sh.
runner_status() {
  local dir="$1" info name url repo label svc pid code proc gh_state busy
  info="$(LC_ALL=C sed $'1s/^\xef\xbb\xbf//' "$dir/.runner" 2>/dev/null || true)" # .NET writes a BOM
  name="$(printf '%s\n' "$info" | sed -n 's/.*"agentName": *"\([^"]*\)".*/\1/p' | head -1)"
  url="$(printf '%s\n' "$info" | sed -n 's/.*"gitHubUrl": *"\([^"]*\)".*/\1/p' | head -1)"
  repo="${url#https://github.com/}"
  printf '\n%s  (%s)\n' "${repo:-$(basename "$dir")}" "$dir"
  if [ -z "$name" ]; then
    echo "  not configured: bash mac-runner.sh add OWNER/REPO"
    return
  fi

  # The launchd label is the plist's name; svc.sh records the plist path in .service.
  label=
  if [ -s "$dir/.service" ]; then label="$(basename "$(cat "$dir/.service")" .plist)"; fi
  [ -n "$label" ] || label="actions.runner.${repo/\//-}.$name"
  label="${label// /_}"
  if svc="$(launchctl print "gui/$(id -u)/$label" 2>/dev/null)"; then
    pid="$(printf '%s\n' "$svc" | awk '$1 == "pid" {print $3; exit}')"
    code="$(printf '%s\n' "$svc" | sed -n 's/^[[:space:]]*last exit code = //p' | head -1)"
    if [ -n "$pid" ]; then echo "  service: running (pid $pid)"
    else echo "  service: loaded but not running (last exit code ${code:-unknown})"; fi
  elif [ -f "$HOME/Library/LaunchAgents/$label.plist" ]; then
    echo "  service: installed but not loaded (log in on the Mac, or: cd $dir && ./svc.sh start)"
  else
    echo "  service: not installed (cd $dir && ./svc.sh install && ./svc.sh start)"
  fi

  proc="$(pgrep -f "$dir/bin/Runner.Listener" 2>/dev/null | head -1 || true)"
  if [ -n "$proc" ]; then echo "  process: Runner.Listener running (pid $proc)"
  else echo "  process: no Runner.Listener running from this folder"; fi

  if ! command -v gh >/dev/null || ! gh auth status >/dev/null 2>&1; then
    echo "  github: unknown (gh not logged in on this Mac)"
    return
  fi
  gh_state="$(gh api "repos/$repo/actions/runners" \
    --jq ".runners[] | select(.name == \"$name\") | \"\(.status) \(.busy)\"" 2>/dev/null || true)"
  if [ -z "$gh_state" ]; then
    echo "  github: $repo has no runner named $name (removed on GitHub? run add again)"
    return
  fi
  busy="${gh_state#* }"
  if [ "${gh_state%% *}" != online ]; then echo "  github: offline as $name"
  elif [ "$busy" = true ]; then
    echo "  github: online as $name, building:"
    gh run list -R "$repo" --status in_progress -L 3 \
      --json workflowName,displayTitle,url --jq '.[] | "    \(.workflowName): \(.displayTitle)  \(.url)"' \
      2>/dev/null || true
  else echo "  github: online as $name, idle (waiting for a job)"; fi
}

cmd_status() {
  brew_env
  xcodebuild -version 2>/dev/null | head -1 || echo "Xcode: not selected"
  for t in brew gh pod jq; do printf '%-6s %s\n' "$t" "$(command -v $t || echo missing)"; done
  [ -d "$RUNNERS" ] || { echo "No runners yet."; return; }
  local dir found=
  for dir in "$RUNNERS"/*/; do
    [ -f "$dir/config.sh" ] || continue
    found=1
    runner_status "${dir%/}"
  done
  [ -n "$found" ] || echo "No runners yet."
}

case "${1:-}" in
  tools) cmd_tools ;;
  add) shift; [ $# -gt 0 ] || die "usage: mac-runner.sh add OWNER/REPO [OWNER/REPO ...]"
       for r in "$@"; do cmd_add "$r"; done ;;
  add-all) cmd_add_all "${2:-}" ;;
  remove) cmd_remove "${2:-}" ;;
  github) cmd_github "${2:-}" ;;
  status) cmd_status ;;
  *) sed -n '2,13p' "$0"; exit 1 ;;
esac
