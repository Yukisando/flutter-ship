# flutter-ship

Ship Flutter apps to Google Play and the App Store (TestFlight) with fastlane and Claude Code.

- **Shared lanes**: each app's `fastlane/Fastfile` imports `fastlane/Fastfile` from this repo, so a fix here reaches every app.
- **Key vault**: upload keystores and Play service account keys are AES-256-GCM encrypted in a private git repo (`ship-vault`). Every machine builds with the same key. You keep one passphrase in your password manager.
- **Version codes from Play**: the next code is the highest one Google Play has ever seen + 1, so two computers never collide. The version name stays in `pubspec.yaml`.
- **Draft by default**: builds go to the internal track as a draft; you roll out (or promote to production) when you want.
- **Store content as files**: listing text, release notes, screenshots, icon and feature graphic live in `fastlane/metadata` (fastlane supply layout). `scripts/shots.py` drives an emulator and renders framed screenshots at store sizes.
- **Claude Code skills**: `ship-setup`, `ship-init`, `ship-listing`, `ship-screenshots`, `ship-android`, `ship-ios`.
- **iOS without a Mac**: Apple keys in the vault, certificate and profile through the App Store Connect API, builds on a GitHub macOS runner, uploads to TestFlight.

## Install

In Claude Code:

```
/plugin marketplace add Yukisando/flutter-ship
/plugin install flutter-ship@flutter-ship
```

Then, in any Flutter project: "set up shipping for this app", "ship it", "promote to production".

## Machine layout

```
~/.ship/config.yml   owner name, vault repo, contact and legal URLs
~/.ship/vault/       clone of the private vault repo
~/.ship/vault.pass   vault passphrase (also in your password manager)
```

Vault layout:

```
.check.enc                         proves the passphrase
android/<package>/upload.jks.enc   upload keystore
android/<package>/signing.json.enc alias and passwords
android/<package>/info.yml         certificate SHA-256 (not secret)
google-play/<name>.json.enc        Play service account key
```

Encryption: PBKDF2-HMAC-SHA256 (200,000 iterations, random salt) and AES-256-GCM, per file.

## Several store accounts

One vault ships to any number of Play and Apple accounts, yours or clients'. Each app's `fastlane/ship.yml` names
the accounts it ships with, and the two stores can differ:

```yaml
play:
  service_account: default   # google-play/default: one Google key, invited by every Play account
ios:
  asc_key: spinlab           # apple/asc/spinlab: that Apple account's key, its team stored with it
```

Adding an account, once:

- **Google Play**: in that account's Play Console, Users and permissions > Invite new users: the service account
  email that `vault_list` prints, with release rights on the account's apps. Nothing changes in the vault:
  one Google key works across Play developer accounts.
- **Apple**: API keys belong to one team. In that account's App Store Connect (as its Admin), Users and Access >
  Integrations > Team Keys > a key with the App Manager role. Then
  `vault_add_asc_key path:AuthKey_X.p8 issuer_id: team_id: name:<account>`.
- **Distribution certificate**: `ios setup` makes one in the team. When the team is at Apple's limit, or its
  existing certificate should be used, `ios certificate import:distribution.p12` imports it instead (it is then
  never replaced silently: when it expires, the lane asks for the new one).
- `owner_name` in ship.yml puts the account holder's name on new upload keys instead of yours.

Ending the work for an account: revoke its Apple key in App Store Connect and remove the service account from
its Play Console. The encrypted files stay in git history, but a revoked key is useless.

## App layout

```
Gemfile, Gemfile.lock                  pinned fastlane
fastlane/Fastfile                      imports the shared lanes
fastlane/ship.yml                      package, locales, track, contact, privacy URL
fastlane/metadata/android/<locale>/    listing, changelogs, images
fastlane/shots/shots.yml, raw/         screenshot plan, captions, raw captures
fastlane/STORE_SETUP.md                one-time Play Console checklist
fastlane/declarations.yml              Data safety, App Privacy, App content answers (ship-declare)
fastlane/ship-done.yml                 steps no API can read, with the day they were done
fastlane/ship-status.json              last `ship_status` result (git-ignored), read by the Ship Board
```

Release signing reads `SHIP_KEYSTORE_*` environment variables set by the lanes: see `templates/android/`.

## Lanes

Run with `bundle exec fastlane <lane>` from the app root. Set `SHIP_LOCAL=/path/to/flutter-ship` to use a local checkout instead of GitHub.

| Lane | What it does |
|---|---|
| `android release [track:] [status:] [metadata:true]` | preflight, next version code, signed `.aab`, upload, git tag |
| `android build` | signed `.aab` only (first manual upload) |
| `android promote [from:] [to:] [status:] [rollout:] [version_code:]` | move a release between tracks, draft on production by default |
| `android metadata` | listing text, images, contact details |
| `android data_safety` | Data safety form from `fastlane/declarations.yml` (`dry:true`: CSV only) |
| `android status` | releases on each track |
| `android version` | next version name and code |
| `android keystore [import:path] [alias:]` | create or import the upload key into the vault |
| `android keystore properties:android/key.properties` | import an existing app's key, passwords read from the file |
| `android preflight` | offline check against Play limits |
| `android doctor` | tools, vault, Play access |
| `ios certificate import:path.p12` | use a distribution certificate the Apple team already has |
| `ios screenshots` | only `fastlane/screenshots/<locale>` to the pubspec version (created if missing), no text; live once that version is approved |
| `products [only:android\|ios]` | create or update the in-app products of `ship.yml` on both stores |
| `vault_add_play_key path: [name:]` | store a service account key in the vault |
| `vault_list` | what the vault holds, without secrets |
| `ship_status [done:id,id]` | where the app stands: Play, App Store, declarations, App Check, budget (ship-status skill); `done:` records hand-made steps |
| `budget_alert [amount:10]` | a monthly budget with email alerts (50/90/100 %, no cap) on the app's Firebase project, unless one covers it |
| `appcheck_ios` | register the iOS app for Firebase App Check with the team DeviceCheck key from the vault |
| `vault_add_devicecheck_key path: team_id:` | store the team DeviceCheck .p8 in the vault |
| `apns_p8 out:` | write the team APNs .p8 from the vault to a file for the Firebase upload (delete it after) |

## In-app products

One-time purchases (non-consumable on the App Store, one-time product on Play) are listed once in `ship.yml`
and `bundle exec fastlane products` creates or updates them on both stores: listing, price, availability, and the
App Store review screenshot. Run it again after any change.

```yaml
products:
  - id: com.example.app.level_pack     # permanent: a store never lets an id be used again
    price: 4.99 EUR                    # an App Store price step in the base territory's currency
    listing:                           # per store language: name max 35, description max 55
      en-US: { name: Level pack, description: Ten extra levels }
    review_screenshot: fastlane/products/level_pack.png   # optional
    review_note: Unlocked from the level map.               # optional
```

- Price: regions in that currency get it exactly; Play converts it for the others. On the App Store the base
  territory is the first of `ios.countries`, and availability follows `ios.countries`.
- Play accepts products only after a build with the billing permission has been uploaded.
- The Play key needs "Manage store presence"; the App Store key the App Manager role.
- The first App Store in-app purchase is reviewed with an app version: add it to the version in App Store
  Connect before Add for Review. The Paid Apps agreement must be active for it to sell.
- Verifying purchases is the app's job (its own server, or a service such as RevenueCat): the lane only manages
  the catalogue.

### Keys for an app's backend (shared by every app)

An app's server checks purchases with two shared keys, so a new app needs no new key and no new invite:

- Play: the service account `play-purchases@coldsnap-ship.iam.gserviceaccount.com`, key in the vault at
  `google-play/purchases`. Invited once in Play Console > Users and permissions with account-wide "View financial
  data" and "Manage orders and subscriptions" only (not Admin). The backend reads it from a secret, e.g.
  `PLAY_PURCHASES_KEY` (Seba: `functions/src/engine/purchases.ts`).
- App Store: the In-App Purchase key "server", in the vault at `apple/iap/server.json.enc` (`APPLE_IAP_KEY` plus
  its key id and issuer id).

The Play account then holds: the owner's own Google accounts (Admin), `google-play/default` (the release key the
lanes and agents use, Admin), and `play-purchases` (purchase checks). A backend's own Firebase or compute account
is never invited.

## iOS builds on your own Mac

Off macOS, `fastlane ios release` starts `.github/workflows/ios-release.yml`. With `mac_runner:` in
`config.yml` (the vault's copy counts) that workflow runs on your own Mac, a self-hosted GitHub
runner: no billed minutes, but the Mac must be on, awake (on the charger it never sleeps) and
logged in. Without `mac_runner:` it runs on GitHub's `macos-26` runners.

```yaml
mac_runner:
  bootstrap_repo: Yukisando/ship-vault       # its runner registers app runners on the Mac
  labels: [self-hosted, macOS, flutter-ship]
```

Once per Mac:

```bash
curl -fsSLO https://raw.githubusercontent.com/Yukisando/flutter-ship/main/scripts/mac-runner.sh
bash mac-runner.sh tools                     # checks Xcode, installs Homebrew, Ruby 3.3, gh, CocoaPods, jq
bash mac-runner.sh add Yukisando/ship-vault  # the bootstrap runner
```

After that nothing is done on the Mac by hand. Before each dispatch, `ios release` / `ios build` /
`ios unity_release`:

1. finds the app repo's runner on the Mac (labels above);
2. if there is none, makes a registration token and starts the vault's `mac-runner.yml`, which runs
   on the bootstrap runner and calls `mac-runner.sh add` for the app (about 30 s);
3. stops with "the Mac is offline" when the runner is not online, instead of queueing forever;
4. sets the repo variable `IOS_RUNNER`, which the workflow templates read for `runs-on`.

`bundle exec fastlane ios runner` does steps 1 to 4 without building. Opting out: `runner:github` on
a lane for one build, `ios.runner: github` in ship.yml for one app, or remove `mac_runner:` for all.
A personal GitHub account cannot share a runner between repos, so each app gets its own idle runner
under `~/actions-runners/` on the Mac. On the Mac itself: `bash mac-runner.sh status`, `remove`,
`github OWNER/REPO` (back to GitHub). Apps whose `ios-release.yml` predates `IOS_RUNNER` build on
GitHub with a warning until the template is copied in.

The runner service cannot read the Mac's own `gh` login from the keychain, so registration tokens
always come from the machine that asks (`RUNNER_TOKEN`). The Mac can also run the lanes directly
(`bundle exec fastlane ios release` builds and uploads locally) when it has the vault and its
passphrase.

## Other CI jobs on your Windows PC

Every job that needs no Apple device (web deploys, Firebase rules and functions, APK builds, cron
checks) can run on your own Windows PC instead of GitHub's `ubuntu-latest`: no billed minutes, but
the PC must be on. iOS stays on the Mac above.

Once per PC, in an elevated PowerShell (services need admin), with `gh` signed in:

```powershell
pwsh -ExecutionPolicy Bypass -File scripts\pc-runner.ps1 exploreum-app SpinLabApp Kokoh
```

For each repo it registers a runner named `ship-pc` (labels `self-hosted, Windows, X64, ship-pc`)
as a Windows service under `C:\actions-runners\<repo>`. A personal account cannot share runners
between repos, so each repo gets its own idle service. The services run as `NETWORK SERVICE` and
start on boot. Re-running the script with a new repo adds it; with an existing one it refreshes the
environment and restarts the service. The services share `C:\actions-runners\_shared`:

- Flutter, Java and the Android SDK come from the usual setup actions (`subosito/flutter-action`,
  `actions/setup-java`, `android-actions/setup-android`) into the shared tool cache, so your own
  Flutter and SDK are never touched by CI and never block a local build;
- pub, Gradle and npm caches; `npm install -g` lands in `_shared\npm-global`, which is on PATH;
- `shell: bash` is Git Bash, npm scripts run in Git Bash, checkouts keep LF.

Then point the repo's workflows at the PC, the same way `IOS_RUNNER` points iOS at the Mac:

```bash
gh variable set PC_RUNNER -R OWNER/REPO --body '["self-hosted","Windows","ship-pc"]'
```

```yaml
defaults:
  run:
    shell: bash                # Git Bash on the PC, bash on ubuntu
jobs:
  deploy:
    # This PC when the repo variable PC_RUNNER is set, else GitHub's ubuntu-latest.
    runs-on: ${{ fromJSON(vars.PC_RUNNER || '"ubuntu-latest"') }}
    steps:
      - uses: subosito/flutter-action@v2
        with:
          channel: stable
          cache: ${{ runner.environment == 'github-hosted' }}   # the PC keeps Flutter itself
      - name: Set up Android SDK (self-hosted)                  # APK builds only
        if: runner.environment == 'self-hosted'
        uses: android-actions/setup-android@v3
```

Things that differ from ubuntu: there is no `google-chrome` (Edge is there); Linux-only tools
need `if: runner.os == 'Linux'`; files written into the workspace (keys, `functions/.env`) stay on
disk until the next checkout, so remove them in an `if: always()` step. A scheduled workflow uses
the copy on the default branch, so a cron job moves to the PC only once the change is merged.
Unset `PC_RUNNER` to go back to GitHub. On a public repo, set fork pull request workflows to need
approval for all outside contributors, or a fork could run code on the PC.

Manage the services with `Get-Service actions.runner.*`; remove one with
`C:\actions-runners\<repo>\config.cmd remove --token <removal token>` in an elevated shell
(`gh api -X POST repos/OWNER/REPO/actions/runners/remove-token --jq .token`).

## CI (later)

Set `SHIP_VAULT_PASSWORD` (and `SHIP_VAULT_DIR` to a checkout of the vault), give the job read access to the vault repo, and run `bundle exec fastlane android release`. Alternatively, set `SHIP_PLAY_JSON` to a key file path to bypass the vault for Play access.
