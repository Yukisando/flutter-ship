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
~/.ship/vaults/<name>/, <name>.pass    a client's own vault, when an app names one (see below)
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

## Client store accounts

Every key is picked per app in `fastlane/ship.yml`, so one machine ships to several Play and Apple accounts:

```yaml
owner_name: Acme SAS                 # name on new upload keys and certificates (default: yours)
vault:                               # optional: the client's own vault
  name: acme                         # ~/.ship/vaults/acme, passphrase in ~/.ship/vaults/acme.pass
  repo: https://github.com/acme/ship-vault.git
play:
  service_account: acme              # google-play/acme in that vault
ios:
  team_id: ABCDE12345                # the client's Apple team
  asc_key: acme                      # apple/asc/acme in that vault
```

- **Google Play**: the client invites a service account email in their Play Console (Users and permissions, only
  their apps). It can be the same service account as yours: one Google key works across Play developer accounts.
- **Apple**: API keys belong to one team. A client admin creates a Team key (App Manager role) and sends the `.p8`:
  `vault_add_asc_key path: issuer_id: name:acme`.
- **Distribution certificate**: `ios setup` makes one in the client's team. When the team is at Apple's limit, or
  the client wants its existing one used, import it: `ios certificate import:distribution.p12`. An imported
  certificate is never replaced silently; when it expires the lane asks for the new one.
- **Separate vault**: without `vault:`, client keys go in your own vault next to every other app's. With it they
  live in their own repo under their own passphrase: the client's CI can read that vault and nothing else, and
  ending the work means handing over or deleting one repo.

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

Set `SHIP_VAULT_PASSWORD` (and `SHIP_VAULT_DIR` to a checkout of the app's vault), give the job read access to the vault repo, and run `bundle exec fastlane android release`. Alternatively, set `SHIP_PLAY_JSON` to a key file path to bypass the vault for Play access.
