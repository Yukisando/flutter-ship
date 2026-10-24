---
name: ship-ios
description: Release a Flutter app to TestFlight / the App Store with flutter-ship - Apple keys in the vault, bundle id, certificate and profile through the App Store Connect API, build on the owner's Mac (self-hosted runner) or a GitHub macOS runner, upload to TestFlight. Use when the user says ship, release, publish or upload the iOS / iPhone app, asks for a TestFlight build, or sets up Apple for an app.
---

# Release to TestFlight

`PLUGIN` is two folders above this file. `FL` = `SHIP_LOCAL=$PLUGIN bundle exec fastlane`. Run from the app root.
iOS builds need macOS. On Windows/Linux, `ios release` and `ios build` start the app's
`.github/workflows/ios-release.yml` instead: on the owner's Mac when `config.yml` has `mac_runner:` (the
lane registers the app's runner there on first use and stops if the Mac is offline), else on a GitHub
`macos-26` runner. Follow it with `gh run watch`. `$FL ios runner` shows where it will build;
`runner:github` builds on GitHub once. README, "iOS builds on your own Mac".

## Default release

1. `git status`: commit first. The runner builds what is pushed, not the working tree.
2. `$FL ios version` prints the version name (pubspec) and the next build number (App Store Connect + 1, or past Play's highest version code when the app is on both stores, so both platforms carry the same number).
3. `$FL ios release`. Wait for the run (`gh run watch <id> -R <repo>`, in the background). It builds a signed .ipa,
   uploads it to TestFlight and pushes a tag `ios/<name>+<number>`.
4. Tell the user: version, build number, and that it appears in TestFlight once Apple has processed it (5-30 min).
5. `$FL ship_status`, and add its open steps to the report (ship-status skill).

## First time for an Apple team or an app

1. Keys, once per team (the user downloads them; never print or paste them):
   - App Store Connect API key (Team Key, App Manager role), once per Apple account:
     `$FL vault_add_asc_key path:<AuthKey_X.p8> issuer_id:<id> team_id:<team> name:<account>`
   - APNs key, if the app uses push: `$FL vault_add_apns_key path:<AuthKey_Y.p8> team_id:<team>`.
     The user also uploads that .p8 in Firebase > Project settings > Cloud Messaging.
2. `fastlane/ship.yml`: an `ios:` block with `asc_key: <account>` (the team comes with the key) and `capabilities`
   (e.g. `[PUSH_NOTIFICATIONS]`; App Store Connect API names: Sign in with Apple is `APPLE_ID_AUTH`, Universal Links
   `ASSOCIATED_DOMAINS`). `vault_list` shows each key's team.
3. `$FL ios setup`: registers the bundle id and capabilities, makes the Apple Distribution certificate (one per team,
   private key only in the vault) and the App Store profile. It says when the App Store Connect app is missing:
   the user creates it by hand (Apps > + > New App, the bundle id, User Access **Limited Access**: Full Access
   shows the new app to every App Store Connect user of the team, such as a colleague added for one app only); Apple's
   API cannot. Check afterwards: Users and Access, each user's apps.
4. Xcode project: `DEVELOPMENT_TEAM`, `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements` (with `aps-environment`
   `production` for push), a deployment target the plugins accept, `UIBackgroundModes` `remote-notification` for FCM,
   `ITSAppUsesNonExemptEncryption` false. Opaque app icons (`remove_alpha_ios: true` with flutter_launcher_icons).
5. CI: copy `$PLUGIN/templates/app/.github/workflows/ios-release.yml`, `.flutter-version`, and `gem "cocoapods"` in the
   Gemfile (`bundle lock --add-platform arm64-darwin x86_64-darwin`). Repository secrets, set without printing them:
   - `SHIP_VAULT_PASSWORD`: `gh secret set SHIP_VAULT_PASSWORD -R <repo> < ~/.ship/vault.pass`
   - `SHIP_VAULT_DEPLOY_KEY`: an ed25519 key made with ssh-keygen, public half added to ship-vault with
     `gh repo deploy-key add ... --allow-write`, private half as the secret, then the local files deleted.
6. `$FL ios build` checks signing on the runner without uploading (the .ipa is kept as an artifact).

## Unity apps

The Unity Editor exports the Xcode project on any OS; only macOS can compile it, so the export travels to a
macOS runner as a zip on a draft GitHub release.

1. In Unity, switch the active platform to iOS first (File > Build Profiles), then build to `build/iOS`.
   An iOS build made while another platform is active skips every `#if UNITY_IOS` post-process step
   (SDK SKAdNetwork ids, Info.plist keys) without an error. ColdSnap's Platform Builder (com.coldsnap.utilities)
   does the switch, the Info.plist keys and the upload button. Version: Unity Player Settings
   (`bundleVersion`, iOS build number); `ios version` reads ProjectSettings when there is no pubspec.
2. Once per app: `ios:` block in ship.yml, `ios setup`, the App Store Connect app, and CI from
   `$PLUGIN/templates/unity/.github/workflows/ios-release.yml` with `gem "cocoapods", ">= 1.16"` in the Gemfile
   (`bundle lock --add-platform arm64-darwin x86_64-darwin`) and the two secrets above (a read-only vault deploy
   key is enough).
3. `$FL ios unity_release` (`xcode:build/iOS` by default): zips the export onto a draft release
   `ios-xcode/<version>+<build>` and starts the workflow, which runs `pod install`, signs Unity-iPhone with the
   profile and UnityFramework with the identity, uploads to TestFlight and deletes the draft.
4. Landscape games: App Store screenshots at 2868x1320 are accepted (`ios preflight` checks both orientations).

## Another Apple account (a client's)

- Being a user (even Admin) on the client's team does not let the vault's other keys in: the account needs its own
  Team Key. Its admin (or the user, when Admin there) makes it and runs
  `$FL vault_add_asc_key path:<p8> issuer_id:<id> team_id:<team> name:<client>`, then `ios.asc_key: <client>`.
- **Apple refused a new distribution certificate / limit reached**: the team already uses its certificates. Ask the
  admin to export one (Keychain Access > the certificate with its key > Export, .p12 with a password) and run
  `$FL ios certificate import:<p12>` with `run_in_terminal`: the password is asked in the terminal, never in chat.
  Then `$FL ios setup`. Delete the .p12 afterwards.

## Listing and submission

- `$FL ios metadata` sends the App Store listing (see ship-listing) and screenshots; `$FL ios status` shows the app,
  its versions and the latest builds with their processing state.
- App Store screenshots: Android raw captures re-framed with `shots.py frame --store ios` are fine (crop the status bar;
  no Android system UI visible).
- iPhone only unless the app is designed for iPad: `TARGETED_DEVICE_FAMILY = 1` in the Runner target. A build that
  also targets iPad makes 13" iPad screenshots mandatory at submission.
- `$FL ios check` lists what App Store Connect still needs before Add for Review: build picked, copyright, listing
  and iPhone screenshots per locale, review contact, sign-in, category, age rating, privacy URL, content rights,
  price, availability. `$FL ios check fix:true` also sets the three the API allows from `ship.yml`
  (`ios.countries: [FRA]`, or `[FRA, ALL]` for every territory; the first code is the price base, free only; `ios.content_rights: third_party|none`).
  `build:N` picks that build for the version once Apple has processed it (state VALID).
  App Privacy (data types) is not in Apple's API: the ship-declare skill writes it through the user's signed-in
  App Store Connect tab. Run `ios check` before telling the user the app is ready to submit.
- App Review may answer "Guideline 2.1 - Information Needed" and ask for a screen recording from a physical device
  on the latest iOS, plus written answers. Name the device from `test_devices.ios` in `~/.ship/config.yml`, never a
  placeholder; ask the user to confirm the iOS version when `checked` is over a month old, then update the field and
  copy the file to the vault. Keep the answers in `fastlane/metadata/ios/review_information/notes.txt` so
  `$FL ios metadata` keeps them in the Notes field for later submissions.
- Picking the build and Add for Review stay manual (App Store Connect > the version > pick the build > Add for Review): write the remaining
  console steps in the app's `fastlane/STORE_SETUP_IOS.md`, click by click with the exact values to type:
  APNs key upload in Firebase, TestFlight testers, Pricing and Availability (price, countries), Content Rights, then the version:
  pick the build, "Sign-in required" (No only when every feature works without an account; a guest mode that
  locks friends or trades still needs a demo account, kept out of git), manual release, Add for Review. Keep the Play
  guide (`fastlane/STORE_SETUP.md`) in the same style and tick what is done.
- Before Add for Review, also check what `ios check` cannot see:
  - Business > Agreements (https://appstoreconnect.apple.com/business): with in-app purchases, Paid Apps must be
    Active. "New" means the user still has to update the legal entity, then sign, then add bank and tax.
  - A first in-app purchase needs its review screenshot (`review_screenshot:` in ship.yml) and is reviewed with the
    version. App Store Connect no longer shows it on the version page: click Add for Review on the version, then
    In-App Purchases > the product > Add for Review > "Draft iOS Submission"; the Draft Submission panel must list the
    version and the product before Submit for Review (Seba, 2026-10-24). Needs Paid Apps Active. Capture the purchase sheet on the emulator (ship-screenshots tools). With no
    Google account there, billing returns no product and apps usually hide the sheet: patch the condition and the price
    label in a throwaway `git worktree` (never the user's checkout), build there, capture, delete the worktree. Then
    crop to the 1290:2796 ratio and scale to 1290x2796 (`products` refuses other sizes). The state can read
    MISSING_METADATA for a minute after the upload; run `products only:ios` again before digging.
  - Firebase App Check: read which Apple provider `lib/main.dart` activates. DeviceCheck registration needs the team
    `.p8` uploaded by the user; App Attest only needs the toggle. Unregistered is harmless until enforcement is on.

## Errors

- **Invalid large app icon ... alpha channel**: flatten the AppIcon PNGs (no transparency).
- **SDK version issue**: the runner's Xcode is too old for App Store Connect: update Xcode on the Mac
  (App Store), or use a newer `macos-*` image on GitHub.
- **"The Mac is offline"**: wake it (charger, logged in), or `runner:github` for this build.
- **`pod install` says the specs repository is too out-of-date**: the Mac workflow refreshes specs before
  building; an app on an older `ios-release.yml` needs the current template.
- **CocoaPods is installed but broken**: `cocoapods` missing from the Gemfile (flutter runs `pod` inside `bundle exec`).
- **No app for <bundle id>**: create it in App Store Connect, then rerun.
- **`ENTITY_ERROR.RELATIONSHIP.INVALID` on appAvailabilities**: Apple wants every territory in the request
  (available true or false); `ios check fix:true` already sends them all.
- **Profile / certificate errors**: rerun `$FL ios setup`; it remakes an expired or revoked certificate or profile and
  pushes it to the vault.
