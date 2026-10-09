---
name: ship-listing
description: Write or update a Flutter app's store listings (Google Play and App Store - title/name, descriptions, keywords, release notes, review notes, age rating) in every listing language, inside fastlane/metadata, and push them to the stores. Use when the user wants store text written, translated, reviewed or uploaded.
---

# Store listing

`PLUGIN` is two folders above this file. Languages come from `locales` in `fastlane/ship.yml`. If the user names other languages, update `locales` first.

## Where the text goes (fastlane supply layout)

```
fastlane/metadata/android/<locale>/
  title.txt               max 30 characters
  short_description.txt   max 80 characters
  full_description.txt    max 4000 characters, plain text (no HTML, no markdown)
  video.txt               optional YouTube URL
  changelogs/default.txt  release notes fallback, max 500
  changelogs/<code>.txt   release notes for one version code
```

## Writing it

1. Learn the app first: README, `lib/` screens and features, l10n strings, marketing material (brochures, websites in the repo), and the existing store listing if there is one.
2. Write each language natively. Do not translate word for word. Use the vocabulary the app's own l10n files use.
3. Title: the app name plus at most a few words of value ("Maya - Ma ville"). No emoji, no "best"/"#1", no price or ranking claims, no ALL CAPS.
4. Short description: one concrete sentence on what the user gets.
5. Full description: hook paragraph, then 4-7 feature lines starting with "• ", then who it is for, then a support or contact line. Mention only features that exist in the code. Google rejects misleading claims and keyword stuffing, and a repeated keyword counts as stuffing.
6. Count characters (`python -c "print(len(open(p,encoding='utf-8').read().strip()))"`) or run `SHIP_LOCAL=$PLUGIN bundle exec fastlane android preflight`.

## Release notes

Before each release, write `changelogs/<code>.txt` for every locale. Get the code from `... android version`. Base the notes on `git log <last android/* tag>..HEAD`. Write 1-4 user-facing lines; skip internal changes. If nothing changed for users, write "Corrections et améliorations." in French or "Bug fixes and improvements." in English. Delete changelog files for old codes only if they clutter the folder.

## App Store (deliver layout)

```
fastlane/metadata/ios/<locale>/
  name.txt               max 30, unique on the App Store: use the name the app record has in App Store Connect
  subtitle.txt           max 30
  description.txt        max 4000, plain text
  keywords.txt           max 100, comma separated with no space after commas (spaces count)
  promotional_text.txt   max 170, editable any time without review
  support_url.txt  marketing_url.txt  privacy_url.txt
  release_notes.txt      not on the first version (Apple refuses "What's New" then)
fastlane/metadata/ios/
  copyright.txt          "2026 Owner Name"
  primary_category.txt   App Store category id: LIFESTYLE, NEWS, UTILITIES, PRODUCTIVITY... (same idea as the Play category)
  review_information/    first_name, last_name, phone_number (+33 ...), email_address, notes
                         demo_user / demo_password only if a login is needed; keep them out of git
  age_rating.json        ageRatingDeclaration attributes (camelCase), e.g. "violenceRealistic": "NONE",
                         "userGeneratedContent": true, "messagingAndChat": false, "advertising": false
fastlane/screenshots/<locale>/*.png   6.9" iPhone 1320x2868 (ship-screenshots, `frame --store ios`)
```

- Reuse the Play text: same features, same tone. Keywords are the App Store's search terms; the name and subtitle already count, do not repeat them.
- Review notes in English: how to reach every feature. If the app has a guest mode, say so; otherwise give a demo account.
- `ios preflight` checks the limits offline.

## Uploading

- Play: `SHIP_LOCAL=$PLUGIN bundle exec fastlane android metadata` sends text, images and contact details. It only works once the app has had its first bundle uploaded (see ship-android). Until then, the files simply wait in git.
- App Store: `SHIP_LOCAL=$PLUGIN bundle exec fastlane ios metadata` sends text, screenshots, age rating and review contact for the pubspec version (it creates or renames the editable version). It does not submit. What the API cannot set goes in the app's `fastlane/STORE_SETUP_IOS.md` for the user: App Privacy answers (map them from the Play data safety form), price, availability, content rights, picking the build, submitting.
