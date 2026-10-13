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
| `android status` | releases on each track |
| `android version` | next version name and code |
| `android keystore [import:path] [alias:]` | create or import the upload key into the vault |
| `android preflight` | offline check against Play limits |
| `android doctor` | tools, vault, Play access |
| `ios certificate import:path.p12` | use a distribution certificate the Apple team already has |
| `vault_add_play_key path: [name:]` | store a service account key in the vault |
| `vault_list` | what the vault holds, without secrets |

## CI (later)

Set `SHIP_VAULT_PASSWORD` (and `SHIP_VAULT_DIR` to a checkout of the vault), give the job read access to the vault repo, and run `bundle exec fastlane android release`. Alternatively, set `SHIP_PLAY_JSON` to a key file path to bypass the vault for Play access.
