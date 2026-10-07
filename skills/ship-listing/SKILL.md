---
name: ship-listing
description: Write or update a Flutter app's store listing (title, short and full description, release notes) in every listing language, inside fastlane/metadata, and push it to Google Play. Use when the user wants store text written, translated, reviewed or uploaded.
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

## Uploading

`SHIP_LOCAL=$PLUGIN bundle exec fastlane android metadata` sends text, images and contact details. It only works once the app has had its first bundle uploaded (see ship-android). Until then, the files simply wait in git.
