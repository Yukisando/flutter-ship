---
name: ship-android
description: Release a Flutter app to Google Play with flutter-ship - next version code, signed bundle from the vault key, release notes, upload as a draft on the test track, and on request promotion to production. Use when the user says ship, release, publish, upload or deploy the Android app, asks for a new Play build, asks what is live, or asks to promote a build to production.
---

# Release to Google Play

`PLUGIN` is two folders above this file. `FL` = `SHIP_LOCAL=$PLUGIN bundle exec fastlane`. Run from the app root.

If `fastlane/ship.yml` is missing, follow ship-init first.

## Default release (no questions needed)

1. `git status`. Uncommitted changes would ship without a matching commit, so commit them or ask the user.
2. `$FL android version` prints the version name (from pubspec) and the next version code. Play is the source of truth: highest code ever uploaded + 1. Any machine gets the same answer, and nothing needs bumping by hand. Bump the version name in `pubspec.yaml` only when the user asks for it (patch / minor / major), then commit.
3. Write the release notes `fastlane/metadata/android/<locale>/changelogs/<code>.txt` for every locale (see ship-listing).
4. `$FL android release`. It runs preflight, pulls the vault, builds with the vault upload key, checks the bundle's signature, uploads to the `play.track` from ship.yml (default `internal`) with status `draft`, and pushes a git tag `android/<name>+<code>`.
   - Add `metadata:true` to also send the listing text and images.
   - If it reports that Play does not know the app yet: the bundle is built. Give the user the printed one-time steps (manual upload in Play Console), then stop.
5. Commit the changelog files.
6. Tell the user: version, track, status, and that the draft is waiting in Play Console > Test and release > <track> (review and roll out there).

A build takes several minutes. Run it in the background and wait.

## Other requests

| User asks | Command |
|---|---|
| What is live / what is on Play | `$FL android status` |
| Is the app ready for production / review | `$FL android check` (validates a production release of the latest test build, changes nothing) |
| Promote to production (draft, the user finishes in the console) | `$FL android promote` |
| Promote and send for review now | `$FL android promote status:completed` (confirm with the user first) |
| Staged rollout | `$FL android promote rollout:0.1` (confirm first) |
| Promote a specific build or between other tracks | `$FL android promote from:internal to:beta version_code:42` |
| Release straight to another track | `$FL android release track:alpha` |
| Only update the store listing | `$FL android metadata` |
| Check everything without uploading | `$FL android doctor` |

A promotion with `status:completed` or a `rollout` reaches real users after Google's review, so confirm it with the user each time. Draft promotions are safe without asking.

## Errors

- **Version code already used**: someone uploaded outside the lanes. `version` reads Play again, so rerun.
- **Signed with ... not the upload key**: the Gradle signing patch is missing or wrong. See `$PLUGIN/templates/android/`.
- **Upload key mismatch on Play** ("signed with the wrong key"): the vault key is not the one Play registered. Compare `$FL vault_list` with Play Console > App integrity > Upload key certificate. Import the right key, or request an upload key reset there.
- **Only releases with status draft may be created on draft app**: the app was never published. Keep `draft` and roll out from the console.
  The first production release is always a draft (`android promote`), sent for review from Publishing overview, which
  also lists any App content form still missing; the API cannot read those forms. `android check` says which case applies.
- **The caller does not have permission**: the service account lacks access to this app in Play Console > Users and permissions.
