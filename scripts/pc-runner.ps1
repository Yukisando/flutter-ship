# flutter-ship pc-runner: registers this Windows PC as a GitHub Actions self-hosted runner for
# each repo given, as a Windows service (NT AUTHORITY\NETWORK SERVICE, starts on boot), under
# C:\actions-runners\<repo>. Labels: self-hosted, Windows, X64, ship-pc. Workflows pick it up
# through the repo variable PC_RUNNER (README: "Other CI jobs on your Windows PC").
#
# Run in an elevated PowerShell (services need admin):
#   pwsh -ExecutionPolicy Bypass -File scripts\pc-runner.ps1 exploreum-app SpinLabApp ...
# Safe to re-run: a repo that already has a runner only gets its .env/.path refreshed and a restart.
# Registration tokens come from `gh` (the signed-in user) and are never printed.
param([Parameter(Mandatory, ValueFromRemainingArguments)][string[]]$Repos, [string]$Owner)
$ErrorActionPreference = 'Stop'
if (-not $Owner) { $Owner = gh api user --jq .login }
$root = 'C:\actions-runners'
$shared = "$root\_shared"
New-Item -ItemType Directory -Force "$root\_dl" | Out-Null
Start-Transcript "$root\pc-runner.log" -Append | Out-Null

# The runner, checked against the SHA-256 GitHub publishes in the release notes.
$release = gh api repos/actions/runner/releases/latest | ConvertFrom-Json
$ver = $release.tag_name.TrimStart('v')
$zip = "$root\_dl\actions-runner-win-x64-$ver.zip"
if (-not (Test-Path $zip)) {
  Invoke-WebRequest "https://github.com/actions/runner/releases/download/v$ver/actions-runner-win-x64-$ver.zip" -OutFile "$zip.part"
  $want = [regex]::Match($release.body, 'BEGIN SHA win-x64 -->([0-9a-f]{64})').Groups[1].Value
  if (-not $want -or (Get-FileHash "$zip.part" -Algorithm SHA256).Hash -ne $want) {
    Remove-Item "$zip.part"
    throw 'The runner download failed its SHA-256 check'
  }
  Move-Item "$zip.part" $zip
}

# Caches every runner shares, writable by the service account.
foreach ($d in 'tool', 'android-sdk', 'pub-cache', 'gradle', 'npm-global', 'npm-cache') {
  New-Item -ItemType Directory -Force "$shared\$d" | Out-Null
}
icacls $shared /grant '*S-1-5-20:(OI)(CI)M' /T /Q | Out-Null   # S-1-5-20 = NETWORK SERVICE

# Tools the jobs need, ahead of the machine PATH. Git\bin first so `shell: bash` is Git Bash,
# never WSL's System32\bash.exe. Flutter, Java and the Android SDK come from setup actions per job,
# into the shared tool cache, so the owner's own Flutter and SDK are never touched.
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$path = @(
  'C:\Program Files\Git\bin', 'C:\Program Files\Git\cmd',
  'C:\Program Files\nodejs', "$shared\npm-global",
  'C:\Python314', 'C:\Python314\Scripts',
  'C:\Program Files\GitHub CLI',
  $machinePath
) -join ';'
# npm scripts run in Git Bash like on Linux; checkouts keep LF like on Linux.
$envFile = @"
RUNNER_TOOL_CACHE=$shared\tool
AGENT_TOOLSDIRECTORY=$shared\tool
ANDROID_HOME=$shared\android-sdk
ANDROID_SDK_ROOT=$shared\android-sdk
PUB_CACHE=$shared\pub-cache
GRADLE_USER_HOME=$shared\gradle
npm_config_prefix=$shared\npm-global
npm_config_cache=$shared\npm-cache
npm_config_script_shell=C:\Program Files\Git\bin\bash.exe
GIT_CONFIG_COUNT=2
GIT_CONFIG_KEY_0=core.autocrlf
GIT_CONFIG_VALUE_0=false
GIT_CONFIG_KEY_1=core.longpaths
GIT_CONFIG_VALUE_1=true
"@

foreach ($repo in $Repos) {
  $dir = "$root\$repo"
  if (-not (Test-Path "$dir\.runner")) {
    New-Item -ItemType Directory -Force $dir | Out-Null
    Expand-Archive $zip $dir -Force
    $token = gh api -X POST "repos/$Owner/$repo/actions/runners/registration-token" --jq .token
    if (-not $token) { throw "No registration token for $Owner/$repo" }
    & "$dir\config.cmd" --unattended --url "https://github.com/$Owner/$repo" --token $token `
      --name ship-pc --labels ship-pc --work _work --runasservice --replace
    $token = $null
    if ($LASTEXITCODE) { throw "config.cmd failed for $repo" }
  }
  Set-Content "$dir\.env" $envFile -Encoding ascii
  Set-Content "$dir\.path" $path -Encoding ascii
  $svc = Get-Content "$dir\.service" -ErrorAction SilentlyContinue
  if ($svc) {
    Set-Service $svc -StartupType Automatic
    Restart-Service $svc
    Write-Host "$repo -> $svc running"
  }
}
Stop-Transcript | Out-Null
