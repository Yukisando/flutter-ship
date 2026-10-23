---
name: ship-declare
description: Fill a Flutter app's store declarations from fastlane/declarations.yml - Play Data safety through the official API, Apple App Privacy through the user's signed-in App Store Connect tab, and the Play App content forms that have no API (privacy policy, ads, sign in details, content rating, target audience, advertising ID, government, financial, health, category) by driving Play Console in the user's browser. Use when the user wants the App content / App Privacy / Data safety / content rating forms filled, or after ship-init on a new app.
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

## 4. First production release (when the user asks to go live)

After `$FL android promote` puts a production draft up, Publishing overview stays locked ("complete the required
steps in the app dashboard") until the dashboard's "Create and publish a release" tasks are done:
- Countries / regions: `.../tracks/production?tab=countryAvailability` > Add countries / regions > tick "Select all
  rows" with a real `left_click` on its coordinates (it is a `mat-checkbox`, JS `.click()` does nothing) > Save.
- Preview and confirm: Production > Releases > Edit release > Next > (read errors with `text()`) > Save.
Then Publishing overview runs quick checks (up to ~15 minutes) before "Send changes for review" unlocks. Sending
reaches real users after Google's review: do it only on the user's explicit go.
