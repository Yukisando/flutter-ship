---
name: ship-status
description: Where every app stands on the way to "fully shipped" - Play production, App Store, store declarations and Firebase security (App Check, APNs, budget alert) - per app with `fastlane ship_status`, and across all apps on the Ship Board dashboard. Use when the user asks what is missing on an app, what to work on today, whether an app is ready for production, for the dashboard, or after any ship-* step to keep the record current.
---

# Ship status

`PLUGIN` is two folders above this file. `FL` = `SHIP_LOCAL=$PLUGIN bundle exec fastlane`. Run from the app root.

## One app

`$FL ship_status` prints one line per step, grouped Google Play / App Store / Security, and writes
`fastlane/ship-status.json` (git-ignored; the lane adds the ignore line). Marks: `[x]` done, `[ ]` to do
(with who does it and where), `[~]` waiting on a store review, `[-]` does not apply, `[?]` could not be read.

Steps are read live wherever an API can tell: Play tracks, App Store versions, Firebase App Check
registration and enforcement (Firebase App Check API with the user's Application Default Credentials,
billed to the app's own project), Cloud Functions enforcement (from `functions/src` and `functions/.env`), billing budgets (Cloud Billing
Budget API, which `budget_alert` turns on in the project).
Steps no API reports are recorded in `fastlane/ship-done.yml` (committed): the lane or skill that does one
records it (`android data_safety` does so itself), and anything done by hand is recorded with
`$FL ship_status done:play_integrity_link,budget_alert`. Recording is additive: it never removes a date.
Record a step only after it was done and checked, never on the user's guess. Play forms a live production
app must have (Data safety, App content, category) and App Privacy of an app Apple reviewed count as done.

A step the user parks on purpose goes in `fastlane/ship.yml` as `hold: {<step id>: <reason>}` (e.g. `ios_live:
TestFlight only until ...`): the lane shows it `[~]` with the reason, the board counts it as waiting, and no skill
works on it (no submission, no fix) until the user removes the line.

**Every ship-* skill ends with `$FL ship_status`** so the record never drifts, and the next step is whatever
the first `[ ]` line says. Do the `Claude:` steps yourself (ship-declare covers the browser ones); list the
`You:` steps for the user with their exact place, in store order.

## All apps: the Ship Board

The dashboard is a Dashboard artifact; its link is `ship_board_url` in `~/.ship/config.yml`. To refresh it:

1. `python $PLUGIN/scripts/ship_board.py <scratchpad>/ship-board.json --refresh` (each app's lane in turn,
   a few minutes; `--only Badalone,Seba` for some). Without `--refresh` it reads the last ship-status.json.
2. Upload the file to the dashboard (Artifact publish, `url` = ship_board_url, `asset: true`,
   `file_path` the JSON), then one ArtifactData `update` of `datasets/steps` with the new `source.url`,
   `source.name` and `updated: {at, by: "ship_board.py"}`. The page itself does not change.
3. Say in a few lines which apps are all green and the open steps worth doing today, `You:` ones first.

The page has a **Today** list: Nathan's open steps whose own prerequisites are done, ranked by how many open
steps of the same app wait on them, then by minutes. The order and the minutes live in `ship_board.py`
(`AFTER`, `MINUTES`, `YOURS`): add a new step there when you add one to the lane. The Open steps table filters by
app and by Yours / Claude's. Nathan never ticks anything on the board. When he says he did a step, check it
(rerun `ship_status`; for a recorded step, look in the console or API first, then `done:<step>`), refresh
the board, and update the skill if the step taught something.

If `ship_board_url` is missing, the board does not exist yet: create it from the Dashboard type
(Artifact quickstart, intent `other`), with a `steps` dataset (the JSON above, attached file) and a page
that shows each app's progress and the open steps, then save its url as `ship_board_url`.

## Order of a full ship

1. Store records exist (you: Play app + first bundle, App Store Connect app).
2. Declarations (ship-declare): Data safety, App content, category and tags, App Privacy.
3. Security: App Check registered on Android and iOS (+ Play Integrity linked), APNs key for push apps,
   budget alert. Then App Check enforced on Firestore / Storage / Auth and Functions, but only once a release
   build that sends App Check tokens is what users run (Firebase > App Check > APIs shows mostly verified
   requests): enforcing earlier locks out installed apps. Enforcement is a change to a live backend: on the
   user's go only.
4. Production: ship-android `promote` + send for review; ship-ios check + submit.
