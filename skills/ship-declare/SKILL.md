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
open the app's App Privacy page (`/apps/<apple id>/distribution/privacy`), then run `apple_privacy.js` (next to this
file) with `javascript_tool`. Set `APP` and `DATA` at its top from `app_privacy:`. It deletes the existing entries,
writes the new ones and prints each status. Reload, check the Product Page Preview, then click Publish and confirm
(Publish states the answers are accurate: do it only on the user's go).

`app_privacy.data` keys are App Store Connect category ids (EMAIL_ADDRESS, NAME, USER_ID, PURCHASE_HISTORY,
GAMEPLAY_CONTENT, OTHER_USER_CONTENT, DEVICE_ID, CRASH_DATA, PERFORMANCE_DATA, PRODUCT_INTERACTION, ...), purposes
are APP_FUNCTIONALITY, ANALYTICS, PRODUCT_PERSONALIZATION, DEVELOPERS_ADVERTISING, THIRD_PARTY_ADVERTISING,
OTHER_PURPOSES. `linked: false` only when the data is never tied to an account (Crashlytics without a user id).
`tracking: true` adds DATA_USED_TO_TRACK_YOU for each tracked category.

## 3. Play App content forms (browser, about 10 minutes)

Use Claude in Chrome in a new tab of the user's browser (they are signed in; never type a password). Start at
`https://play.google.com/console/u/0/developers/<dev id>/app/<app id>/app-content/overview`: the ids are in the URL
after opening the app. Each form has a fixed path under `app-content/`:

| Form | Path | Notes |
|---|---|---|
| Privacy policy | `privacy-policy` | type the URL, Save |
| Ads | `ads-declaration` | Yes / No radio |
| Sign in details | `testing-credentials` | "restricted" if any feature needs an account (Google cannot create one). Credentials: the user types them |
| Content rating | `content-rating-overview` > Start questionnaire | email, category, IARC terms checkbox, then sections that open one by one |
| Target audience | `target-audience-content` | needs Sign in details done first |
| Advertising ID | `ad-id-declaration` | No unless an ads/Analytics SDK adds the AD_ID permission |
| Government apps | `government-apps` | |
| Financial features | `finance` | "My app doesn't provide any financial features" > Next > Save |
| Health apps | `health` | "My app does not have any health features" > Next > Save |
| Category | `../store-settings` | App category > Edit |

What makes it fast and reliable:
- Read the page with `javascript_tool` (`main.innerText`), not screenshots. `get_page_text` returns only the menu.
- Click radios and checkboxes with `javascript_tool`: find the `input` whose ancestor text contains the question,
  then `.click()`. The content rating questionnaire reveals each follow-up only after the previous answer, so answer,
  wait ~1 s, read again.
- Save buttons re-render once the form changes: find Save after editing, or click it by its text in JS.
- After each Save a "Go to Publishing overview?" dialog opens: press Escape.
- Nothing goes live until the user sends the changes for review from Publishing overview. Leave that to them.

Order for a new app: the user creates the app and uploads the first bundle; if a feature needs an account they fill
Sign in details (they type the password); then this skill does the rest, Target audience included. Use the same demo
accounts for App Store Connect > the version > App Review Information.

Record every answer given in the browser back into `declarations.yml` (`play_content:`), with the resulting ratings.
