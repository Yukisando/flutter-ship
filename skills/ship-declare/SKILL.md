---
name: ship-declare
description: Fill a Flutter app's store declarations from fastlane/declarations.yml - Play Data safety through the official API, Apple App Privacy through the user's signed-in App Store Connect tab, and the Play App content forms that have no API (privacy policy, ads, sign in details, content rating, target audience, advertising ID, government, financial, health, category, tags) by driving Play Console in the user's browser, plus Firebase App Check registration (Play Integrity, DeviceCheck) and the other security steps ship_status lists. Use when the user wants the App content / App Privacy / Data safety / content rating forms filled, or after ship-init on a new app.
---

# Store declarations

`PLUGIN` is two folders above this file. `FL` = `SHIP_LOCAL=$PLUGIN bundle exec fastlane`. Run from the app root.

Everything comes from `fastlane/declarations.yml` (see Seba's for a full example). Write it from the code first:
Firebase Auth (email, user ids, guest mode), Firestore fields, Crashlytics (is a user id set?), Analytics, ads SDKs,
purchases, push tokens, location, camera, chat, friends. Anything that is a judgment about content (violence, nudity,
fear, loot boxes) is the user's call: ask with AskUserQuestion, never guess. Commit the file.

Play only accepts App content changes for an app that exists in Play Console; Apple needs the app record.

## 1. Play Data safety (official API, seconds)

`$FL android data_safety` fills Play's own CSV template (`$PLUGIN/templates/play/data_safety_template.csv`) from
`data_safety:` and posts it to `applications.dataSafety`. `dry:true` only writes `fastlane/data_safety.csv`.
It replaces the whole form. Verify once: App content > Data safety > Export to CSV, and compare the values.
When Play adds questions, export a blank form from any app and replace the template.

## 2. Apple App Privacy (the user's App Store Connect session)

Apple's API has no App Privacy endpoint. App Store Connect's own web API does, and it works from any page of
appstoreconnect.apple.com where the user is signed in, so no Apple ID or 2FA is needed here. With Claude in Chrome,
open any App Store Connect page and run `apple_privacy.js` (next to this file) with `javascript_tool`. Set `BUNDLE`
and `DATA` at its top from `app_privacy:`; it finds the Apple id itself. It deletes the existing entries, writes the
new ones and prints each status (201 = written). Publish stays a click for the user on the app's App Privacy page
(`/apps/<apple id>/distribution/privacy`): it states the answers are accurate, and a scripted PATCH of
`appDataUsagesPublishState` is refused by the permission classifier.

`app_privacy.data` keys are App Store Connect category ids (EMAIL_ADDRESS, NAME, USER_ID, PURCHASE_HISTORY,
GAMEPLAY_CONTENT, OTHER_USER_CONTENT, DEVICE_ID, CRASH_DATA, PERFORMANCE_DATA, PRODUCT_INTERACTION, ...), purposes
are APP_FUNCTIONALITY, ANALYTICS, PRODUCT_PERSONALIZATION, DEVELOPERS_ADVERTISING, THIRD_PARTY_ADVERTISING,
OTHER_PURPOSES. `linked: false` only when the data is never tied to an account (Crashlytics without a user id).
`tracking: true` adds DATA_USED_TO_TRACK_YOU for each tracked category.

## 3. Play App content forms (browser, about 10 minutes)

Use Claude in Chrome in a new tab of the user's browser (they are signed in; never type a password). Find the ids
without screenshots: open `https://play.google.com/console/u/0/developers/<dev id>/app-list` and read the links
(`[...document.querySelectorAll('a[href*="/app/"]')]`) next to the package name; open the developer account from
`/console/u/0/developers` if the dev id is unknown. Each form has a fixed path under
`.../app/<app id>/app-content/`:

| Form | Path | Notes |
|---|---|---|
| Privacy policy | `privacy-policy` | type the URL, Save |
| Ads | `ads-declaration` | Yes / No radio |
| Sign in details | `testing-credentials` | "restricted" if any feature needs an account Google cannot create itself (invite only, verified email). An open in-app sign-up (any email, no verification) is No. Credentials: the user types them |
| Content rating | `content-rating-overview` > Start questionnaire | email, category, IARC terms checkbox, then sections that open one by one |
| Target audience | `target-audience-content` | needs Sign in details done first |
| Advertising ID | `ad-id-declaration` | No unless an ads/Analytics SDK adds the AD_ID permission |
| Government apps | `government-apps` | |
| Financial features | `finance` | "My app doesn't provide any financial features" > Next > Save |
| Health apps | `health` | "My app does not have any health features" > Next > Save |
| Category | `../store-settings` | App category > Edit |
| Tags | `../store-settings` | Manage tags > `await setTags(play_content.tags)` > `btn('Apply')`; saves at once. Up to 5, from Play's own list (it has Card, Trivia, Casual, Educational, but no Collectible): an unknown name is reported, pick the nearest |

What makes it fast and reliable (one `browser_batch` per form: navigate, wait 3 s, inject, answer, save, read back):
- Paste `play_forms.js` (next to this file) into `javascript_tool` on each form page, then use `inputs()`,
  `pick(/label/)`, `btn('Next')`, `save()`, `buttons()`, `text()`. No screenshots needed. `main` is often null and
  `get_page_text` returns only the menu.
- Content rating: set the email, `pick(/^Game The app/)`, `pick(/I agree to the Terms/)`, `btn('Next')`, then
  `await answerIarc(/interact|communicat|exchange/i)` answers the whole questionnaire in one call (Yes only where
  the regex matches; put the yes topics of `content_rating:` in it) and returns each answer. Check the list, then
  `save()`, `btn('Next')` (Next stays disabled until Save), read the ratings from `text()`, `save()`.
- A password manager overlay on an email field blocks the extension ("Cannot access a chrome-extension:// URL"):
  set the value in JS with the native setter (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')
  .set.call(e, v)` plus `input` and `change` events) instead of clicking or typing. If it already appeared, reload.
- After each Save a "Go to Publishing overview?" dialog opens: press Escape, or just navigate on.
- Check: App content overview > Actioned tab lists every done form; Need attention should be empty.

Order for a new app: the user creates the app and uploads the first bundle; if a feature needs an account they fill
Sign in details (they type the password); then this skill does the rest, Target audience included. Use the same demo
accounts for App Store Connect > the version > App Review Information.

Record every answer given in the browser back into `declarations.yml` (`play_content:`), with the resulting ratings.
Then record the steps in the app's status: `$FL ship_status done:play_app_content,play_store_settings` (Data safety
records itself; add `ios_app_privacy` once the user says they clicked Publish).

## 4. Security: App Check (every Firebase app, before production)

App Check proves a request comes from the real app on a real device, so a script cannot create accounts or call
Functions in bulk. `$FL ship_status` shows each step; do the `Claude:` ones, list the `You:` ones.
- Android: Firebase console > App Check > the Android app > Play Integrity: the **app signing** SHA-256 from Play
  Console > Test and release > App signing (`.../keymanagement`; the page's first fingerprint, not the upload key),
  tick the terms, Save. Claude can do this in the browser; the fingerprint is read, never typed by guess.
- Play Integrity link (Claude, browser): `.../app/<app id>/protect-with-play` > Play Integrity API > Get started
  (lands on `.../app-integrity/integrity-api-settings`) > Link Cloud project > "Enter project number manually" > the
  `project_number` from `android/app/google-services.json` > Link project. The dropdown lists only projects the
  Play account can see. The dialog stays open on failure without a message: read the result with
  `read_network_requests` (`integrityApiLinkedCloudProjects:link`). 403 = the Play Console Google account has no IAM
  role on that Cloud project (it happens when Firebase lives on another Google account): the user grants it in
  Google Cloud > IAM, Claude does not change IAM. Record `play_integrity_link`.
- iOS (DeviceCheck): one key per Apple team, made once by the user: Apple Developer > Keys > + > tick DeviceCheck
  (Apple keys never gain a service later, and the .p8 downloads only once), then
  `$FL vault_add_devicecheck_key path:AuthKey_X.p8 team_id:` and delete the file. After that each app is a Claude
  step: `$FL appcheck_ios` sends the vault key to Firebase App Check (`deviceCheckConfig` PATCH, nothing printed).
  The app's code must use `AppleDeviceCheckProvider` (or `AppleProvider.deviceCheck` in firebase_app_check 0.3).
  App Attest registrations do not show in the API, so ship_status only sees DeviceCheck.
- Push apps: the team APNs key in Firebase > Project settings > Cloud Messaging
  (`console.firebase.google.com/u/<n>/project/<id>/settings/cloudmessaging`; `u/<n>` is the Google account that
  owns the project, try u/0 then u/1) > Apple app > Production APNs auth key > Upload. There is no API. With the
  user's permission rule for it, Claude runs `$FL apns_p8 out:<scratch>/AuthKey_<id>.p8`, uploads it with
  `file_upload` in the dialog (Key ID and team come from the lane output), and deletes the file at once. Without
  that rule the vault read is refused, and it stays a You step. Never print or paste the key. Record `apns_key`.
  Tried 2026-10-23: the dialog's Browse opens the OS file picker straight away (no `<input type=file>` in the page or
  a shadow root, and hooking createElement or `showOpenFilePicker` caught nothing), so `file_upload` has no target and
  it stays a **You** step: upload the .p8 (Key ID 57MMKAKCLS, team 7LX2P3K976) by hand, then Claude checks and
  records it. Don't decrypt the key for it. The permission rule must be `Bash(bundle exec fastlane apns_p8:*)`
  (a bare command string is not a rule). The lane writes only into an existing folder: `mkdir -p` first.
- Budget alert (Claude): `$FL budget_alert` (amount:10). Firebase already makes a 1-unit "Firebase Project <id>"
  budget when a project moves to Blaze, so the lane usually only confirms it; ship_status reads budgets live. The
  Budget API is billed to the app's project and is off there at first: the lane turns it on (serviceusage) and waits.
  Email alerts to billing admins at 50/90/100 %, never a cap. Console: `console.cloud.google.com/billing/<acct>/budgets`.
- App Privacy state (Claude, read only): in any App Store Connect tab, `/iris/v1/apps?filter[bundleId]=<bundle>` for
  the id, then `/iris/v1/apps/<id>/dataUsages?limit=500` (rows) and `/iris/v1/apps/<id>/dataUsagePublishState`
  (`published`). Compare the rows to `app_privacy:` before running apple_privacy.js (it deletes and rewrites), and
  record `ios_app_privacy` when `published` is true. Publish itself stays the user's click.
- Before filling Play forms, open App content > Actioned: forms done earlier are listed there with their date.
- Enforcement (Firestore, Storage, Authentication in App Check > APIs; `enforceAppCheck` on Functions callables) comes
  last, on the user's go, once the release that sends tokens is what users run: see ship-status.
- Release builds must activate App Check with the real providers and debug builds with the debug ones
  (`AndroidDebugProvider`, `AppleDebugProvider`, `WebDebugProvider()`), whose tokens go in App Check > Manage debug
  tokens. Skip desktop, and wrap `activate` in try/catch so a failure never blocks startup.
- Web (Claude, API, any app served on the web): a reCAPTCHA Enterprise **score** key, then register it. With ADC
  and `x-goog-user-project: <project id>`: enable `recaptchaenterprise.googleapis.com` (serviceusage `:enable`),
  `POST recaptchaenterprise.googleapis.com/v1/projects/<id>/keys` with `webSettings.integrationType: SCORE` and
  `allowedDomains` = every host that serves a client using that Firebase **web app id** (hosting sites, custom
  domains, preview/staging channels such as `<site>--staging-<hash>.web.app`, `*.firebaseapp.com`, an admin portal
  or App Hosting `*.hosted.app` that reuses the same web app id, and `localhost`; subdomains match, other labels do
  not), then `PATCH firebaseappcheck.googleapis.com/v1/projects/<id>/apps/<web app id>/recaptchaEnterpriseConfig
  ?updateMask=siteKey` with `{"siteKey": ...}`. The site key is public: a constant in the app code is fine. Code:
  `providerWeb: kDebugMode ? WebDebugProvider() : ReCaptchaEnterpriseProvider(siteKey)`. Check every other web
  client of the same project (a Next.js admin on the JS SDK needs `initializeAppCheck` with
  `ReCaptchaEnterpriseProvider` too), or enforcement locks it out. Cost: reCAPTCHA Enterprise is free up to 10,000
  assessments a month; one assessment per token, default TTL 1 hour per browser session.

## 5. First production release (when the user asks to go live)

After `$FL android promote` puts a production draft up, Publishing overview stays locked ("complete the required
steps in the app dashboard") until the dashboard's "Create and publish a release" tasks are done:
- Countries / regions: `.../tracks/production?tab=countryAvailability` > Add countries / regions > tick "Select all
  rows" with `await tick(document.querySelector('[role=checkbox][aria-label="Select all rows"]'))` (a
  `mat-checkbox`: plain `.click()` does nothing) > Save.
- Preview and confirm: Production > Releases > Edit release > Next > (read errors with `text()`) > Save.
Then Publishing overview runs quick checks (up to ~15 minutes) before "Send changes for review" unlocks. Sending
reaches real users after Google's review: do it only on the user's explicit go.
Order matters (Seba, 2026-10-23): do Edit release > Next > Save first, then the countries. With managed publishing
off, saving the countries sends them (and any pending App content change) for review at once, and the release
draft then has to join that review: Publishing overview > "Submit 1 change for review" opens "Do you want to
restart your review?". Restart only when that review is the one just started in this session (its date is today
and you made it); never restart a review that was already waiting, it puts the app back at the end of the queue.

## 6. App Store submission and App Privacy Publish (on the user's go)

- App Privacy Publish: `/apps/<apple id>/distribution/privacy` > Publish (`find` "Publish button") > Publish in the
  confirm dialog. Check with `/iris/v1/apps/<id>/dataUsagePublishState` (`published: true`). Record `ios_app_privacy`.
- Add for Review: `$FL ios check build:<n>` first (it must print no missing item), then
  `/apps/<apple id>/distribution/ios/version/inflight` > Add for Review (top right) > the Draft Submission panel
  lists the version > Submit for Review > "1 Item Submitted". `ios status` then shows WAITING_FOR_REVIEW.
- Age rating: Apple adds questions (parental controls, age assurance, messaging, advertising, ...). An unanswered
  one blocks Add for Review with "You must respond to the required age ratings questions", and `ios check` names
  it. Answer in App Information (`/apps/<id>/distribution/info`) > Age Ratings > Set Up / Edit: a 7-step dialog of
  radio groups named after the attributes (`value` "false"/"true" or "NONE"/"INFREQUENT_OR_MILD"/...). Answer
  from the app's content (the user decides anything that is a judgment), step by step (clicking Next detaches the
  script), then read back `/iris/v1/apps/<id>/appInfos?include=ageRatingDeclaration`.
- A rejected submission: `/iris/v1/reviewSubmissions?filter[app]=<id>` shows state UNRESOLVED_ISSUES; the message is
  on `/apps/<id>/distribution/reviewsubmissions/details/<submission id>` (`get_page_text`). Fix metadata or code
  yourself; a guideline that asks for a business or legal answer (5.1.1(ix) seller / organization account, proof of
  authorization) is the user's: quote it and stop.
- Never on an app whose version is already WAITING_FOR_REVIEW or IN_REVIEW: a new version, another build, a
  metadata save or a resubmission there can cancel the review. Read `ios status` first.
- Sign-in for review with a demo account: the user types the password in App Store Connect > App Review
  Information (or keeps it in the gitignored `review_information/demo_*.txt` for `ios metadata`); Claude never types it.

## 7. App Check enforcement (on the user's go, per app and per service)

Registration is safe; enforcement refuses every client that sends no valid token. Read the state first:
`GET firebaseappcheck.googleapis.com/v1beta/projects/<id>/services/<service>` (no `enforcementMode` = OFF).

Hold enforcement until **all** of these hold, and say which one is missing:
1. Every client people run sends tokens:
   - Android: the Play **production** release contains the `FirebaseAppCheck.instance.activate` commit
     (`git merge-base --is-ancestor <commit> <release tag>`), and most installs have updated (Play Console >
     Statistics > by app version; old versions get no token and break on enforcement).
   - iOS: same for the App Store build, with a DeviceCheck (or App Attest) key registered for the iOS app.
   - Web: the deployed web build activates `ReCaptchaEnterpriseProvider` with a key registered for the web app, and
     every host that serves it is in the key's allowed domains. Also every other web client on the same project
     (admin portal, landing page with Firebase calls). A `kIsWeb` skip on a live site means hold.
   - App Check > Apps shows no "Register remaining apps" banner.
2. Metrics: App Check > APIs (`/u/<n>/project/<id>/appcheck/products`, the owner account), per service, show
   **verified requests above ~95%** for **at least 3 days in a row** after the last client shipped. "Metrics will be
   displayed when ..." means no data yet: hold. Unverified traffic left over is old app versions, scripts or bots:
   look at which before going on.
3. Debug tokens: the user's own debug builds (each phone, emulator and browser that runs debug builds) are in App
   Check > Apps > Manage debug tokens, so development keeps working after enforcement.
4. Then enforce **one service at a time**, in this order, with a day or more between each:
   **Storage first** (least damage if wrong: images fail, data stays), **then Firestore**, **then Authentication**
   (enforcing it blocks sign-in for clients without tokens, the worst failure). For each: App Check > APIs > the
   service > Enforce (or `PATCH .../services/<service>?updateMask=enforcementMode` with
   `{"enforcementMode":"ENFORCED"}`, only on the user's go), then watch for an hour: the APIs page (rejected
   requests should be only the unverified share seen before), the web app and both phone apps loading data and
   images, signing in, and Crashlytics / client error logs. Rollback is instant: Unenforce (`"OFF"`).
5. Functions callables: `enforceAppCheck: true` (or `ENFORCE_APP_CHECK=true` in `functions/.env`), deploy with
   `FUNCTIONS_DISCOVERY_TIMEOUT=60` and the app's own gcloud quota project, after the three services are stable.
`$FL ship_status` reads enforcement live (`appcheck_enforced`): run it after each service.
