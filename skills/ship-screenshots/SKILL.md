---
name: ship-screenshots
description: Produce store screenshots, the 512px icon and the feature graphic for a Flutter app automatically - boot an emulator, drive the app through adb, capture screens in each listing language, then render framed images with captions at the exact Play (and App Store) sizes. Use when the user wants screenshots or store graphics made or refreshed.
---

# Screenshots and store graphics

`PLUGIN` is two folders above this file. `SHOTS` = `python $PLUGIN/scripts/shots.py`. Run it from the app root. Run `$SHOTS --help` for all commands.

The goal is zero user actions. Drive the app yourself and look at every capture with the Read tool before keeping it.

## 1. Plan

Read the app: main screens, the strongest features, what the listing promises. Pick 4-6 shots. Order them by selling power: what the app is for first, then features. Avoid login screens, empty states and permission dialogs. Write `fastlane/shots/shots.yml`:

```yaml
icon: assets/icon.png          # largest square source of the launcher icon (see flutter_launcher_icons image_path)
style:
  background: ["#FFF4D6", "#FFD27A"]   # gradient from the app's brand colours (theme file)
  text: "#3A2A00"                      # caption colour with strong contrast
  icon_background: "#FFFFFF"           # optional: fill behind a transparent icon
  # font: assets/fonts/Brand-Bold.ttf  # optional: the app's display font (default Poppins Bold)
feature_graphic:
  tagline: { fr-FR: "...", en-US: "..." }
shots:
  - id: home
    caption: { fr-FR: "Toute votre ville dans votre poche", en-US: "Your whole town in your pocket" }
```

Captions: 2-6 words, a benefit rather than a feature name, written natively per locale.

## 2. Device

1. `$SHOTS boot` starts the first AVD if no device is connected. Phones need a 9:16 or taller screen (any Pixel AVD).
2. Build and install a release-like APK without the debug banner: `flutter build apk --release` (debug signing is fine for local screenshots), then `$SHOTS install build/app/outputs/flutter-apk/app-release.apk`.
3. `$SHOTS prep` sets a clean status bar (10:00, full battery and signal, no notifications).

## 3. Data and login

Screens need realistic content. In order of preference:
1. Use the project's seed or demo data (look for `seed`, `demo`, `fixtures`, `tools/`, credential files like `*credentials*.local.*`). Use a demo or test account only, never a real user's account.
2. If the app needs sign-in, sign in through the UI with the demo account: `tap-text`, then `type`.
3. If no demo data exists, ask the user once whether to create a demo account or seed data.

Content shown in screenshots is public. No real people's personal data, no internal tooling, no placeholder lorem ipsum.

## 4. Capture loop (per locale)

For each locale in `shots.yml`:
1. `$SHOTS launch <package> --locale <locale>`. This sets the per-app language (Android 13+) and restarts the app.
2. For each shot: navigate with `$SHOTS ui` (on-screen elements with tap coordinates), `tap-text "Label"`, `tap X Y`, `swipe`, `key back`. Wait for images and animations to settle (`sleep 2`), then
   `$SHOTS capture fastlane/shots/raw/<locale>/phone/<id>.png`.
3. Open the PNG with Read. Retake it if anything is off: loading spinner, keyboard open, toast, half-scrolled list, wrong language, debug banner, or personal data.

For tablet screenshots (optional on Play, needed for the App Store iPad), boot a tablet AVD and save to `raw/<locale>/tablet/<id>.png`.

`$SHOTS unprep` when done.

## 5. Render

```
$SHOTS frame                # Play: metadata/android/<locale>/images/phoneScreenshots (1080x1920, max 8)
$SHOTS frame --store ios    # App Store: fastlane/screenshots/<locale> (6.9" iPhone, 13" iPad)
$SHOTS graphics             # icon.png 512x512 and featureGraphic.png 1024x500 per locale
```

Open at least the first rendered screenshot and the feature graphic with Read and check them: caption contrast, nothing cut off, colours on brand. Adjust `style` and re-render as needed. Then run `SHIP_LOCAL=$PLUGIN bundle exec fastlane android preflight`.

Commit `fastlane/shots/` (config + raw captures) and the rendered images, so any machine can re-render without recapturing.
