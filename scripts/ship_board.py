"""Collect every app's ship status into one file for the Ship Board dashboard.

Each app that has fastlane/ship.yml under the projects folder (~/.ship/config.yml
`projects_dir`, default ~/Documents/Projects) is checked with `fastlane ship_status`,
which writes fastlane/ship-status.json. This script runs that lane in each app
(--refresh) or only reads the files already there, and writes one JSON array of rows,
one per app and step, to the path given.

    python ship_board.py out.json [--refresh] [--only Badalone,Seba]
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

import yaml

PLUGIN = pathlib.Path(__file__).resolve().parent.parent

# What each step waits for (same app), so the board can rank the quick steps that unblock the most work.
AFTER = {
    "play_production": ["play_app", "play_data_safety", "play_app_content", "play_store_settings"],
    "play_data_safety": ["play_app"], "play_app_content": ["play_app"], "play_store_settings": ["play_app"],
    "play_integrity_link": ["play_app"], "appcheck_android": ["play_app"],
    "ios_app_privacy": ["ios_app"], "ios_live": ["ios_app", "ios_app_privacy"],
    "appcheck_enforced": ["appcheck_android", "appcheck_ios"],
    "appcheck_functions": ["appcheck_android", "appcheck_ios"],
}
# Rough minutes a step takes Nathan by hand (the board's "today" list shows the quick ones first).
MINUTES = {"play_app": 20, "ios_app": 5, "ios_app_privacy": 1, "appcheck_ios": 10, "apns_key": 5, "budget_alert": 3}
# Who acts. Steps whose how text says "You:" are Nathan's.
YOURS: set[str] = set()


def who(step: str, how: str) -> str:
    return "you" if step in YOURS or how.startswith("You") else "claude"


def projects_dir() -> pathlib.Path:
    config = pathlib.Path.home() / ".ship" / "config.yml"
    data = yaml.safe_load(config.read_text(encoding="utf-8")) if config.exists() else {}
    return pathlib.Path(os.path.expanduser((data or {}).get("projects_dir", "~/Documents/Projects")))


def apps(only: set[str]) -> list[pathlib.Path]:
    found = sorted(p.parent.parent for p in projects_dir().glob("*/fastlane/ship.yml"))
    return [a for a in found if not only or a.name in only]


def refresh(app: pathlib.Path) -> str | None:
    env = {**os.environ, "SHIP_LOCAL": str(PLUGIN)}
    run = subprocess.run(["bundle", "exec", "fastlane", "ship_status"], cwd=app, env=env,
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         shell=os.name == "nt", timeout=300)
    return None if run.returncode == 0 else (run.stdout + run.stderr).strip().splitlines()[-1][:200]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--refresh", action="store_true", help="run fastlane ship_status in each app first")
    ap.add_argument("--only", default="", help="comma-separated app folder names")
    args = ap.parse_args()
    rows = []
    for app in apps({n for n in args.only.split(",") if n}):
        error = refresh(app) if args.refresh else None
        status_file = app / "fastlane" / "ship-status.json"
        if error or not status_file.exists():
            print(f"{app.name}: {error or 'no ship-status.json (run with --refresh)'}", file=sys.stderr)
            continue
        report = json.loads(status_file.read_text(encoding="utf-8"))
        for item in report["items"]:
            rows.append({
                "app": report["app"], "folder": report["folder"], "checked_at": report["checked_at"],
                "group": item["group"], "step": item["id"], "title": item["title"], "state": item["state"],
                "detail": item.get("detail") or "", "how": item.get("how") or "",
                "who": who(item["id"], item.get("how") or ""), "after": ",".join(AFTER.get(item["id"], [])),
                "minutes": MINUTES.get(item["id"], 5),
            })
        print(f"{app.name}: {report['ok']}/{report['total']}")
    pathlib.Path(args.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
