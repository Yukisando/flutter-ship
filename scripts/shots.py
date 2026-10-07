#!/usr/bin/env python3
"""flutter-ship screenshots: drive an Android device, capture raw screens, render store images.

Device commands (an emulator or phone over adb):
  shots.py devices | boot [--avd NAME] | prep | unprep
  shots.py install APK | launch PACKAGE [--locale fr-FR] | stop PACKAGE | geo LAT LON
  shots.py ui | tap X Y | tap-text LABEL | swipe X1 Y1 X2 Y2 [MS] | type TEXT | key back|home|enter
  shots.py capture OUT.png

Store images, from <project>/fastlane/shots/shots.yml and raw captures in
<project>/fastlane/shots/raw/<locale>/{phone,tablet}/<id>.png:
  shots.py frame [--project DIR] [--store android|ios|all]
  shots.py graphics [--project DIR]          Play icon (512) and feature graphic (1024x500)

Global: -s SERIAL picks a device when several are connected.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
FONT = PLUGIN / "fonts" / "Poppins-Bold.ttf"
FONT_LIGHT = PLUGIN / "fonts" / "Poppins-SemiBold.ttf"

# (store, folder, width, height, raw kind). Play takes 9:16 at 1080+ for promotion on phones and
# tablets; the App Store sizes are the ones it currently requires (6.9" iPhone, 13" iPad).
TARGETS = [
    ("android", "phoneScreenshots", 1080, 1920, "phone"),
    ("android", "sevenInchScreenshots", 1200, 1920, "tablet"),
    ("android", "tenInchScreenshots", 1600, 2560, "tablet"),
    ("ios", "APP_IPHONE_69", 1320, 2868, "phone"),
    ("ios", "APP_IPAD_PRO_129", 2064, 2752, "tablet"),
]

# ---------------------------------------------------------------- adb


def adb_path():
    candidates = []
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(var):
            candidates.append(Path(os.environ[var]) / "platform-tools")
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools")
    candidates += [Path.home() / "Library/Android/sdk/platform-tools", Path.home() / "Android/Sdk/platform-tools"]
    exe = "adb.exe" if os.name == "nt" else "adb"
    for d in candidates:
        if (d / exe).is_file():
            return str(d / exe)
    found = shutil.which("adb")
    if not found:
        sys.exit("adb not found: install the Android SDK platform-tools or set ANDROID_HOME")
    return found


SERIAL = None


def adb(*args, binary=False, check=True):
    cmd = [adb_path()] + (["-s", SERIAL] if SERIAL else []) + [str(a) for a in args]
    res = subprocess.run(cmd, capture_output=True)
    if check and res.returncode != 0:
        sys.exit(f"adb {' '.join(map(str, args))} failed: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout if binary else res.stdout.decode(errors="replace")


def shell(*args, check=True):
    return adb("shell", *args, check=check)


def cmd_devices(_):
    print(adb("devices", "-l").strip())


def cmd_boot(a):
    if "\tdevice" in adb("devices"):
        print("A device is already connected")
        return
    sdk = Path(adb_path()).parent.parent
    emulator = sdk / "emulator" / ("emulator.exe" if os.name == "nt" else "emulator")
    avds = subprocess.run([str(emulator), "-list-avds"], capture_output=True, text=True).stdout.split()
    avd = a.avd or (avds[0] if avds else None)
    if not avd:
        sys.exit("No Android Virtual Device. Create one in Android Studio > Device Manager.")
    cmd = [str(emulator), "-avd", avd, "-no-snapshot-save", "-no-boot-anim"]
    if os.name == "nt":
        # Break away from the caller's job object, or the emulator dies with the shell that
        # started it. Some hosts forbid breakaway: then run `boot` from a terminal that stays open.
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags | 0x01000000)
        except PermissionError:
            print("Note: the emulator will close when this shell's job ends.")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    else:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    adb("wait-for-device")
    for _ in range(180):
        if shell("getprop", "sys.boot_completed", check=False).strip() == "1":
            print(f"{avd} booted")
            return
        time.sleep(1)
    sys.exit("Emulator did not finish booting in 3 minutes")


def demo(command, **extras):
    args = ["am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", command]
    for k, v in extras.items():
        args += ["-e", k, v]
    shell(*args)


def cmd_prep(_):
    """Clean status bar: 10:00, full battery and signal, no notification icons."""
    shell("settings", "put", "global", "sysui_demo_allowed", "1")
    demo("enter")
    demo("clock", hhmm="1000")
    demo("battery", level="100", plugged="false")
    demo("network", wifi="show", level="4")
    demo("network", mobile="show", datatype="none", level="4")
    demo("notifications", visible="false")
    print("Demo status bar on")


def cmd_unprep(_):
    demo("exit")
    print("Demo status bar off")


def cmd_geo(a):
    """Emulator GPS position, so maps and "my location" show the app's own town."""
    print(adb("emu", "geo", "fix", a.lon, a.lat).strip())


def cmd_install(a):
    print(adb("install", "-r", "-g", a.apk).strip())


def cmd_launch(a):
    if a.locale:
        # Per-app language (Android 13+): the app restarts in that locale, the device stays as is.
        shell("cmd", "locale", "set-app-locales", a.package, "--locales", a.locale)
    shell("am", "force-stop", a.package)
    shell("monkey", "-p", a.package, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(a.wait)
    print(f"Launched {a.package}" + (f" in {a.locale}" if a.locale else ""))


def cmd_stop(a):
    shell("am", "force-stop", a.package)


def ui_nodes():
    shell("uiautomator", "dump", "/sdcard/ship-ui.xml", check=False)
    xml = adb("exec-out", "cat", "/sdcard/ship-ui.xml")
    start = xml.find("<?xml")
    if start < 0:
        sys.exit("Could not read the screen layout (is the screen animating?). Try again.")
    nodes = []
    for n in ET.fromstring(xml[start:]).iter("node"):
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        label = (n.get("text") or n.get("content-desc") or "").replace("\n", " ").strip()
        clickable = n.get("clickable") == "true" or n.get("long-clickable") == "true"
        scrollable = n.get("scrollable") == "true"
        if label or clickable or scrollable or n.get("class", "").endswith("EditText"):
            nodes.append({"label": label, "x": (x1 + x2) // 2, "y": (y1 + y2) // 2, "clickable": clickable,
                          "scrollable": scrollable, "edit": n.get("class", "").endswith("EditText"),
                          "bounds": (x1, y1, x2, y2)})
    return nodes


def cmd_ui(_):
    for n in ui_nodes():
        flags = ",".join(f for f, on in (("tap", n["clickable"]), ("scroll", n["scrollable"]), ("input", n["edit"])) if on)
        print(f"({n['x']},{n['y']}) [{flags}] {n['label']!r}")


def cmd_tap(a):
    shell("input", "tap", a.x, a.y)


def cmd_tap_text(a):
    wanted = a.label.lower()
    nodes = ui_nodes()
    match = next((n for n in nodes if n["label"].lower() == wanted), None) or \
        next((n for n in nodes if wanted in n["label"].lower()), None)
    if not match:
        sys.exit(f"Nothing labelled {a.label!r} on screen")
    shell("input", "tap", match["x"], match["y"])
    print(f"Tapped {match['label']!r} at ({match['x']},{match['y']})")


def cmd_swipe(a):
    shell("input", "swipe", a.x1, a.y1, a.x2, a.y2, a.ms)


def cmd_type(a):
    # adb input text needs spaces as %s and shell metacharacters escaped.
    text = re.sub(r"([\\'\"`$&|;<>()])", r"\\\1", a.text).replace(" ", "%s")
    shell("input", "text", text)


def cmd_key(a):
    codes = {"back": "KEYCODE_BACK", "home": "KEYCODE_HOME", "enter": "KEYCODE_ENTER", "tab": "KEYCODE_TAB"}
    shell("input", "keyevent", codes.get(a.key, a.key))


def cmd_capture(a):
    png = adb("exec-out", "screencap", "-p", binary=True)
    if not png.startswith(b"\x89PNG"):
        sys.exit("screencap returned no image")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    print(f"Saved {out}")


# ---------------------------------------------------------------- rendering


def pil():
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: F401
    except ImportError:
        sys.exit("Pillow is missing: python -m pip install pillow pyyaml")
    import PIL
    return PIL


def load_config(project):
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML is missing: python -m pip install pillow pyyaml")
    path = project / "fastlane" / "shots" / "shots.yml"
    if not path.exists():
        sys.exit(f"No {path}. The ship-screenshots skill writes it.")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ship = yaml.safe_load((project / "fastlane" / "ship.yml").read_text(encoding="utf-8")) or {}
    cfg.setdefault("locales", ship.get("locales", ["en-US"]))
    cfg.setdefault("app_name", ship.get("app_name", ""))
    return cfg


def color(value):
    from PIL import ImageColor
    return ImageColor.getrgb(value)


def gradient(size, colors):
    from PIL import Image
    w, h = size
    colors = [color(c) for c in (colors if isinstance(colors, list) else [colors])]
    if len(colors) == 1:
        return Image.new("RGB", size, colors[0])
    top, bottom = colors[0], colors[-1]
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return column.resize(size)


def font(cfg, size, light=False):
    from PIL import ImageFont
    style = cfg.get("style", {})
    custom = style.get("font_light" if light else "font")
    path = Path(custom) if custom else (FONT_LIGHT if light else FONT)
    if custom and not path.is_absolute():
        path = Path(cfg["_project"]) / path
    return ImageFont.truetype(str(path), size)


def wrap(draw, text, fnt, width):
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=fnt) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_text_block(canvas, cfg, text, top, size, max_lines=3, light=False):
    """Centered caption starting at `top`; shrinks until it fits in max_lines. Returns bottom y."""
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    w = canvas.width
    width = w * 0.86
    while True:
        fnt = font(cfg, size, light)
        lines = wrap(draw, text, fnt, width)
        if len(lines) <= max_lines or size < 20:
            break
        size = int(size * 0.92)
    fill = color(cfg.get("style", {}).get("text", "#ffffff"))
    y = top
    for line in lines:
        lw = draw.textlength(line, font=fnt)
        draw.text(((w - lw) / 2, y), line, font=fnt, fill=fill)
        y += int(size * 1.22)
    return y


def rounded(img, radius):
    from PIL import Image, ImageDraw
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def device(shot, width):
    """Screenshot inside a thin dark bezel with rounded corners."""
    from PIL import Image, ImageDraw
    bezel = max(6, int(width * 0.022))
    inner_w = width - 2 * bezel
    inner_h = round(shot.height * inner_w / shot.width)
    screen = rounded(shot.convert("RGB").resize((inner_w, inner_h), Image.LANCZOS), int(inner_w * 0.06))
    body = Image.new("RGBA", (width, inner_h + 2 * bezel), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle((0, 0, body.width - 1, body.height - 1), int(width * 0.075),
                                           fill=(17, 17, 17, 255))
    body.alpha_composite(screen, (bezel, bezel))
    return body


def paste_with_shadow(canvas, layer, x, y):
    from PIL import Image, ImageFilter
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    alpha = layer.split()[-1].point(lambda a: int(a * 0.35))
    blur = max(8, layer.width // 25)
    shadow.paste((0, 0, 0, 255), (x, y + blur // 2), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    base = canvas.convert("RGBA")
    base.alpha_composite(shadow)
    base.alpha_composite(layer, (x, y))
    return base.convert("RGB")


def redact(shot, boxes):
    """Blur each [x1, y1, x2, y2] box (raw pixels) inside an ellipse: avatars, names, emails."""
    from PIL import Image, ImageDraw, ImageFilter
    shot = shot.convert("RGB")
    for x1, y1, x2, y2 in boxes or []:
        region = shot.crop((x1, y1, x2, y2))
        blurred = region.filter(ImageFilter.GaussianBlur(max(x2 - x1, y2 - y1) / 4))
        mask = Image.new("L", region.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, region.width - 1, region.height - 1), fill=255)
        shot.paste(blurred, (x1, y1), mask)
    return shot


def render_shot(cfg, raw_path, caption, size, boxes=None):
    from PIL import Image
    w, h = size
    canvas = gradient(size, cfg.get("style", {}).get("background", ["#222222", "#000000"]))
    shot = redact(Image.open(raw_path), boxes)
    # crop_top: drop the status bar (its height in raw pixels), whose icons often clash with the app.
    top_crop = int(cfg.get("style", {}).get("crop_top", 0))
    if top_crop:
        shot = shot.crop((0, top_crop, shot.width, shot.height))
    pad = int(w * 0.07)
    top = int(h * 0.055)
    if caption:
        top = draw_text_block(canvas, cfg, caption, top, int(w * 0.066)) + int(h * 0.025)
    avail_w, avail_h = w - 2 * pad, h - top - int(h * 0.04)
    dev_w = int(min(avail_w, avail_h * shot.width / shot.height))
    layer = device(shot, dev_w)
    if layer.height > avail_h:
        layer = layer.resize((int(layer.width * avail_h / layer.height), avail_h))
    return paste_with_shadow(canvas, layer, (w - layer.width) // 2, top)


def localized(value, locale, default_locale):
    if isinstance(value, dict):
        return value.get(locale) or value.get(locale.split("-")[0]) or value.get(default_locale) or ""
    return value or ""


def cmd_frame(a):
    pil()
    project = Path(a.project).resolve()
    cfg = load_config(project)
    cfg["_project"] = str(project)
    shots_dir = project / "fastlane" / "shots" / "raw"
    default_locale = cfg["locales"][0]
    written = 0
    for locale in cfg["locales"]:
        for store, folder, w, h, kind in TARGETS:
            if a.store not in ("all", store):
                continue
            entries = [s for s in cfg.get("shots", []) if (shots_dir / locale / kind / f"{s['id']}.png").exists()
                       or (shots_dir / default_locale / kind / f"{s['id']}.png").exists()]
            if store == "android":
                out_dir = project / "fastlane" / "metadata" / "android" / locale / "images" / folder
            else:
                out_dir = project / "fastlane" / "screenshots" / locale
            if not entries:
                continue
            if store == "android" and out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            entries = entries[:8 if store == "android" else 10]
            for i, s in enumerate(entries, 1):
                raw = shots_dir / locale / kind / f"{s['id']}.png"
                if not raw.exists():
                    raw = shots_dir / default_locale / kind / f"{s['id']}.png"
                boxes = s.get("redact")
                if isinstance(boxes, dict):
                    boxes = boxes.get(locale) or boxes.get(default_locale)
                image = render_shot(cfg, raw, localized(s.get("caption"), locale, default_locale), (w, h), boxes)
                name = f"{i:02d}_{s['id']}.png" if store == "android" else f"{i:02d}_{s['id']}_{folder}.png"
                image.save(out_dir / name, optimize=True)
                written += 1
            print(f"{locale} {folder}: {len(entries)} images")
    if not written:
        sys.exit(f"No raw captures found under {shots_dir}/<locale>/phone/")


def cmd_graphics(a):
    pil()
    from PIL import Image
    project = Path(a.project).resolve()
    cfg = load_config(project)
    cfg["_project"] = str(project)
    icon_src = cfg.get("icon")
    if not icon_src:
        sys.exit("shots.yml needs icon: path/to/1024px-icon.png")
    icon = Image.open(project / icon_src).convert("RGBA")
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    bg = cfg.get("style", {}).get("icon_background")
    if bg:
        filled = Image.new("RGBA", square.size, color(bg) + (255,))
        filled.alpha_composite(square)
        square = filled
    play_icon = square.resize((512, 512), Image.LANCZOS)
    default_locale = cfg["locales"][0]
    feature = cfg.get("feature_graphic", {})
    for locale in cfg["locales"]:
        images = project / "fastlane" / "metadata" / "android" / locale / "images"
        images.mkdir(parents=True, exist_ok=True)
        play_icon.save(images / "icon.png")
        fg = gradient((1024, 500), feature.get("background") or cfg.get("style", {}).get("background", ["#222", "#000"]))
        size = 270
        mark = rounded(square.resize((size, size), Image.LANCZOS).convert("RGB"), int(size * 0.22)) \
            if bg else square.resize((size, size), Image.LANCZOS)
        fg = paste_with_shadow(fg, mark, 70, (500 - size) // 2)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(fg)
        left = 70 + size + 55
        width = 1024 - left - 50
        title = cfg.get("app_name", "")
        tagline = localized(feature.get("tagline"), locale, default_locale)
        title_font = font(cfg, 84)
        while draw.textlength(title, font=title_font) > width and title_font.size > 30:
            title_font = font(cfg, int(title_font.size * 0.92))
        tag_font = font(cfg, 34, light=True)
        tag_lines = wrap(draw, tagline, tag_font, width)[:3] if tagline else []
        block = title_font.size * 1.1 + len(tag_lines) * 34 * 1.3 + (18 if tag_lines else 0)
        y = (500 - block) / 2
        fill = color(cfg.get("style", {}).get("text", "#ffffff"))
        draw.text((left, y), title, font=title_font, fill=fill)
        y += title_font.size * 1.1 + 18
        for line in tag_lines:
            draw.text((left, y), line, font=tag_font, fill=fill)
            y += 34 * 1.3
        fg.convert("RGB").save(images / "featureGraphic.png", optimize=True)
        print(f"{locale}: icon.png 512x512, featureGraphic.png 1024x500")


# ---------------------------------------------------------------- cli


def main():
    global SERIAL
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-s", "--serial")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices").set_defaults(fn=cmd_devices)
    b = sub.add_parser("boot"); b.add_argument("--avd"); b.set_defaults(fn=cmd_boot)
    sub.add_parser("prep").set_defaults(fn=cmd_prep)
    sub.add_parser("unprep").set_defaults(fn=cmd_unprep)
    ge = sub.add_parser("geo"); ge.add_argument("lat"); ge.add_argument("lon"); ge.set_defaults(fn=cmd_geo)
    i = sub.add_parser("install"); i.add_argument("apk"); i.set_defaults(fn=cmd_install)
    l = sub.add_parser("launch"); l.add_argument("package"); l.add_argument("--locale")
    l.add_argument("--wait", type=float, default=4); l.set_defaults(fn=cmd_launch)
    s = sub.add_parser("stop"); s.add_argument("package"); s.set_defaults(fn=cmd_stop)
    sub.add_parser("ui").set_defaults(fn=cmd_ui)
    t = sub.add_parser("tap"); t.add_argument("x"); t.add_argument("y"); t.set_defaults(fn=cmd_tap)
    tt = sub.add_parser("tap-text"); tt.add_argument("label"); tt.set_defaults(fn=cmd_tap_text)
    sw = sub.add_parser("swipe")
    for n in ("x1", "y1", "x2", "y2"):
        sw.add_argument(n)
    sw.add_argument("ms", nargs="?", default="300"); sw.set_defaults(fn=cmd_swipe)
    ty = sub.add_parser("type"); ty.add_argument("text"); ty.set_defaults(fn=cmd_type)
    k = sub.add_parser("key"); k.add_argument("key"); k.set_defaults(fn=cmd_key)
    c = sub.add_parser("capture"); c.add_argument("out"); c.set_defaults(fn=cmd_capture)
    f = sub.add_parser("frame"); f.add_argument("--project", default=".")
    f.add_argument("--store", default="android", choices=["android", "ios", "all"]); f.set_defaults(fn=cmd_frame)
    g = sub.add_parser("graphics"); g.add_argument("--project", default="."); g.set_defaults(fn=cmd_graphics)
    a = p.parse_args()
    SERIAL = a.serial
    # Labels can hold any language; a Windows console code page would mangle them.
    sys.stdout.reconfigure(encoding="utf-8")
    a.fn(a)


if __name__ == "__main__":
    main()
