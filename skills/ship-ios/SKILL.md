---
name: ship-ios
description: Release a Flutter app to TestFlight / the App Store with flutter-ship - Apple keys in the vault, bundle id, certificate and profile through the App Store Connect API, build on a GitHub macOS runner, upload to TestFlight. Use when the user says ship, release, publish or upload the iOS / iPhone app, asks for a TestFlight build, or sets up Apple for an app.
---

# Release to TestFlight

`PLUGIN` is two folders above this file. `FL` = `SHIP_LOCAL=$PLUGIN bundle exec fastlane`. Run from the app root.
iOS builds need macOS. On Windows/Linux, `ios release` and `ios build` start the app's
`.github/workflows/ios-release.yml` on a GitHub `macos-26` runner instead; follow it with `gh run watch`.

## Default release

1. `git status`: commit first. The runner builds what is pushed, not the working tree.
2. `$FL ios version` prints the version name (pubspec) and the next build number (App Store Connect + 1).
3. `$FL ios release`. Wait for the run (`gh run watch <id> -R <repo>`, in the background). It builds a signed .ipa,
   uploads it to TestFlight and pushes a tag `ios/<name>+<number>`.
4. Tell the user: version, build number, and that it appears in TestFlight once Apple has processed it (5-30 min).

## First time for an Apple team or an app

1. Keys, once per team (the user downloads them; never print or paste them):
   - App Store Connect API key (App Manager role): `$FL vault_add_asc_key path:<AuthKey_X.p8> issuer_id:<id>`
   - APNs key, if the app uses push: `$FL vault_add_apns_key path:<AuthKey_Y.p8> team_id:<team>`.
     The user also uploads that .p8 in Firebase > Project settings > Cloud Messaging.
2. `fastlane/ship.yml`: an `ios:` block with `team_id`, `asc_key: default`, `capabilities` (e.g. `[PUSH_NOTIFICATIONS]`).
3. `$FL ios setup`: registers the bundle id and capabilities, makes the Apple Distribution certificate (one per team,
   private key only in the vault) and the App Store profile. It says when the App Store Connect app is missing:
   the user creates it by hand (Apps > + > New App, the bundle id); Apple's API cannot.
4. Xcode project: `DEVELOPMENT_TEAM`, `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements` (with `aps-environment`
   `production` for push), a deployment target the plugins accept, `UIBackgroundModes` `remote-notification` for FCM,
   `ITSAppUsesNonExemptEncryption` false. Opaque app icons (`remove_alpha_ios: true` with flutter_launcher_icons).
5. CI: copy `$PLUGIN/templates/app/.github/workflows/ios-release.yml`, `.flutter-version`, and `gem "cocoapods"` in the
   Gemfile (`bundle lock --add-platform arm64-darwin x86_64-darwin`). Repository secrets, set without printing them:
   - `SHIP_VAULT_PASSWORD`: `gh secret set SHIP_VAULT_PASSWORD -R <repo> < ~/.ship/vault.pass`
   - `SHIP_VAULT_DEPLOY_KEY`: an ed25519 key made with ssh-keygen, public half added to ship-vault with
     `gh repo deploy-key add ... --allow-write`, private half as the secret, then the local files deleted.
6. `$FL ios build` checks signing on the runner without uploading (the .ipa is kept as an artifact).

## Listing and submission

- `$FL ios metadata` sends the App Store listing (see ship-listing) and screenshots; `$FL ios status` shows the app,
  its versions and the latest builds with their processing state.
- App Store screenshots: Android raw captures re-framed with `shots.py frame --store ios` are fine (crop the status bar;
  no Android system UI visible).
- iPhone only unless the app is designed for iPad: `TARGETED_DEVICE_FAMILY = 1` in the Runner target. A build that
  also targets iPad makes 13" iPad screenshots mandatory at submission.
- Submitting stays manual (App Store Connect > the version > pick the build > Add for Review): write the remaining
  console steps in the app's `fastlane/STORE_SETUP_IOS.md`, click by click with the exact values to type:
  APNs key upload in Firebase, TestFlight testers, Pricing and Availability (price, countries), App Privacy (every data
  type with purpose / linked / tracking, derived from the Play data safety answers), Content Rights, then the version:
  pick the build, "Sign-in required" (No when a guest mode exists, else a demo account kept out of git), manual
  release, Add for Review. Keep the Play guide (`fastlane/STORE_SETUP.md`) in the same style and tick what is done.

## Errors

- **Invalid large app icon ... alpha channel**: flatten the AppIcon PNGs (no transparency).
- **SDK version issue**: the runner's Xcode is too old for App Store Connect; use a newer `macos-*` image.
- **CocoaPods is installed but broken**: `cocoapods` missing from the Gemfile (flutter runs `pod` inside `bundle exec`).
- **No app for <bundle id>**: create it in App Store Connect, then rerun.
- **Profile / certificate errors**: rerun `$FL ios setup`; it remakes an expired or revoked certificate or profile and
  pushes it to the vault.
