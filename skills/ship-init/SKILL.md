---
name: ship-init
description: Onboard a Flutter app to flutter-ship - fastlane folder, ship.yml, vault-backed release signing, store listing, screenshots and the Play Console checklist. Use when the user wants to publish or ship a Flutter app that has no fastlane/ship.yml yet.
---

# Onboard a Flutter app

`PLUGIN` is two folders above this file. Run every fastlane command from the app root with `SHIP_LOCAL=$PLUGIN bundle exec fastlane ...`, so the lanes come from this installed plugin.

Do as much as possible without asking. Ask only the questions below. Use AskUserQuestion with the defaults pre-selected.

## 0. Machine

If `~/.ship/config.yml` or `~/.ship/vault.pass` is missing, follow the ship-setup skill first.

## 1. Questions (one AskUserQuestion call)

- **Listing languages**: default `fr-FR` + `en-US`. The first one is the default listing language. Offer the languages the app is localised in (`lib/l10n/*.arb`, `l10n.yaml`).
- **Upload key**: "New app (create a key)" (default), or "Already on Play: import the existing keystore". If importing, ask for the `.jks` path.
- **Store accounts**: which Play and Apple accounts the app ships to (they may differ). List what the vault knows with `vault_list`. A new account is added once (README, "Several store accounts"): its Play Console invites the service account email `vault_list` prints, and its Apple key goes in with `vault_add_asc_key ... name:<account>`. Set `play.service_account` and `ios.asc_key` in ship.yml, and `owner_name` when the account holder is a client.

Read everything else from the project:
- `package_name`: `applicationId` in `android/app/build.gradle(.kts)`. Stop if it is `com.example.*`: Play rejects it, and the package name can never change after the first upload. Propose a name and confirm it with the user.
- `app_name`: `android:label` in `AndroidManifest.xml`.
- `privacy_url` and terms URL: search the code first (`privacy`, `confidentialite`, `legal`). Prefer an app-specific policy when one exists. Otherwise use the owner's pages from `~/.ship/config.yml`:
  - `legal.generic_url`: shared policies, with `privacy/`, `tos/` and `delete-account/` under it.
  - `legal.website_repo` + `legal.app_path`: a local website repo where app-specific pages can be added, e.g. `apps/{slug}/privacy/`. Copy the generic page's structure. Commit and push only after the user agrees, because it publishes.
- `contact.email`, `contact.website`: from existing legal pages or ~/.ship/config.yml (`contact_email`). If neither has them, ask the user.

## 2. Files

1. Copy `$PLUGIN/templates/app/Gemfile` to the app root, and `$PLUGIN/templates/app/fastlane/{Fastfile,ship.yml}` to `fastlane/`. Fill in `ship.yml`.
2. Run `bundle install`. Commit `Gemfile` and `Gemfile.lock`: every machine then uses the same fastlane version.
3. Patch the release signing in `android/app/build.gradle(.kts)` with `$PLUGIN/templates/android/signing.gradle(.kts)`. Replace the existing `buildTypes.release.signingConfig` line. Keep everything else.
4. Add to `.gitignore`: `fastlane/report.xml`, `fastlane/README.md`, `*.jks`, `*.keystore`, `key.properties`.
5. If `android/key.properties` or a keystore file sits in the project, it may be the app's existing upload key. Offer to import it into the vault (`keystore import:<path>`). Do not delete it without asking.

## 3. Upload key

- New app: `SHIP_LOCAL=$PLUGIN bundle exec fastlane android keystore`. This creates an RSA 4096 PKCS12 key with a random password and pushes it to the vault.
- Existing app: `... android keystore import:<path>`. The passwords are asked in the terminal, so run it with `run_in_terminal` (or give the user the command). Never ask for keystore passwords in chat.

Then run `... android doctor`.

## 4. Store content

1. Listing text: follow the ship-listing skill.
2. Screenshots, icon and feature graphic: follow the ship-screenshots skill.
3. Run `... android preflight` until it passes.

## 5. Play Console checklist

Write `fastlane/declarations.yml` (the store declarations: Data safety, App Privacy, App content answers) as the ship-declare skill describes. Once the app exists in Play Console, ship-declare fills those forms; they are no longer manual steps.

Write `fastlane/STORE_SETUP.md` from the template below for what stays manual. Fill in the real values. A filled value saves the user from thinking. Make each step paste-ready.

```markdown
# <App> - Google Play setup (one time)

Console: https://play.google.com/console

- [ ] **Create the app**: Home > Create app. Name: <app_name>. Default language: <default locale>. App. Free. Tick both declarations.
- [ ] **First bundle** (Google only lets the API manage an app after one manual upload): run `bundle exec fastlane android build`, then Test and release > Testing > Internal testing > Create new release > keep "Use Google-generated key" > upload `build/app/outputs/bundle/release/app-release.aab` > Save. From then on: `bundle exec fastlane android release`.
- [ ] **Internal testers**: Internal testing > Testers > add an email list (yourself at least).
- [ ] **App content and Data safety**: filled by Claude from `fastlane/declarations.yml` (ship-declare), once the app exists.
- [ ] **Sign in details** (only when a feature needs an account): App content > Sign in details > a demo account the reviewers can use. You type the password; keep it out of git.
- [ ] **Closed test** (only personal accounts created after 13 Nov 2023): 12+ testers opted in for 14 days before production access. Leave this line out for an organization account; the owner's own Play account is one, so its apps never need it.
```

To fill declarations.yml, read the code: Firebase Auth (email, user IDs, guest mode), Firestore fields, Analytics/Crashlytics, location, camera and photos, push tokens. Ask the user the content questions (violence, nudity, loot boxes) rather than guessing.

## 6. Finish

Commit the fastlane folder, metadata, signing patch and Gemfile with a clear message. Then run `... ship_status`: it is the app's checklist from here on (stores, declarations, App Check, budget). Tell the user only what remains for them: the unchecked STORE_SETUP.md items and the `You:` lines of ship_status, in order.
