"""Collect every app's ship status into one file for the Ship Board dashboard.

Each app that has fastlane/ship.yml under the projects folder (~/.ship/config.yml
`projects_dir`, default ~/Documents/Projects) is checked with `fastlane ship_status`,
which writes fastlane/ship-status.json. This script runs that lane in each app
(--refresh) or only reads the files already there, and writes one JSON array of rows,
one per app and step, to the path given.

Websites listed under `websites:` in ~/.ship/config.yml get their own rows (group Website):
HTTPS, redirects, sitemap, Search Console, a portfolio entry for every app, the asset
version stamp and each app's privacy page, all read live.

    websites:
      coldsnap.fr:
        url: https://coldsnap.fr
        repo: ~/Documents/Projects/yukisando.github.io
        root: coldsnap                        # site folder inside the repo
        portfolio: coldsnap/data/projects.js  # an app opts out with `portfolio: false` in ship.yml

    python ship_board.py out.json [--refresh] [--only Badalone,Seba]
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

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


def http(url: str) -> tuple[int, str]:
    """Status and redirect target of one GET, without following redirects."""
    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    req = urllib.request.Request(url, headers={"User-Agent": "flutter-ship ship_board"})
    try:
        with urllib.request.build_opener(NoFollow).open(req, timeout=20) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location") or ""
    except OSError as e:
        return 0, str(e)[:120]


def website_rows(name: str, site: dict) -> list[dict]:
    """Live checks for one website from ~/.ship/config.yml `websites:` (read-only HTTP and the local repo)."""
    url = site["url"].rstrip("/")
    host = url.split("://", 1)[1]
    repo = pathlib.Path(os.path.expanduser(site["repo"]))
    web_root = repo / site.get("root", "")
    items = []

    def item(step, title, ok, detail, how, minutes=5):
        items.append({"id": step, "title": title, "state": "ok" if ok else "todo", "detail": detail,
                      "how": "" if ok else how, "minutes": minutes})

    code, _ = http(url + "/")
    item("site_live", "Site answers over HTTPS", code == 200, f"{url}/ -> {code}", "Claude: check the hosting and DNS")
    code, loc = http(f"http://{host}/")
    item("https_redirect", "http:// redirects to https://", code in (301, 308) and loc.startswith("https://"),
         f"http -> {code} {loc}", "Claude: turn on Enforce HTTPS in the Pages settings")
    code, loc = http(f"https://www.{host}/")
    item("www_redirect", "www redirects to the bare domain", code in (301, 308) and loc.startswith(url),
         f"www -> {code} {loc}", "Claude: add a www redirect at the DNS provider")
    code, _ = http(url + "/sitemap.xml")
    sitemap = code == 200
    try:
        req = urllib.request.Request(url + "/robots.txt", headers={"User-Agent": "flutter-ship ship_board"})
        robots = "sitemap:" in urllib.request.urlopen(req, timeout=20).read().decode().lower()
    except OSError:
        robots = False
    item("sitemap", "sitemap.xml served and named in robots.txt", sitemap and robots,
         f"sitemap {'ok' if sitemap else 'missing'}, robots {'names it' if robots else 'does not name it'}",
         "Claude: add sitemap.xml and a Sitemap: line in robots.txt")
    verified = any(web_root.glob("google*.html"))
    item("search_console", "Google Search Console verified", verified,
         "verification file in the repo" if verified else "no google*.html in the site folder",
         "You: Search Console > Add property > HTML file, then Claude commits the file", 10)

    portfolio = (repo / site["portfolio"]).read_text(encoding="utf-8") if site.get("portfolio") else ""
    if portfolio:
        missing = []
        for app in apps(set()):
            ship = yaml.safe_load((app / "fastlane" / "ship.yml").read_text(encoding="utf-8")) or {}
            if not ship.get("package_name") or ship.get("portfolio") is False:
                continue
            if ship["package_name"] not in portfolio and f"id: '{app.name.lower()}" not in portfolio:
                missing.append(ship.get("app_name") or app.name)
        item("portfolio_apps", "Every shipped app has a portfolio entry", not missing,
             "missing: " + ", ".join(missing) if missing else "all apps listed",
             "Claude: add the entry with store screenshots (data/projects.js)", 20)
        # Browsers keep the old projects.js until the ?v= stamp in index.html changes.
        index = (web_root / "index.html").read_text(encoding="utf-8")
        stamp = max(re.findall(r"\?v=(\d{8})", index) or ["0"])
        changed = subprocess.run(["git", "log", "-1", "--format=%cs", "--", site["portfolio"]], cwd=repo,
                                 capture_output=True, text=True).stdout.strip().replace("-", "")
        item("asset_version", "Asset version newer than the last portfolio change", stamp >= changed,
             f"?v={stamp}, portfolio changed {changed}", "Claude: bump ?v= in index.html", 2)

    legal = []
    for app in apps(set()):
        ship = yaml.safe_load((app / "fastlane" / "ship.yml").read_text(encoding="utf-8")) or {}
        if ship.get("privacy_url") and http(ship["privacy_url"])[0] != 200:
            legal.append(ship.get("app_name") or app.name)
    item("privacy_pages", "Every app's privacy policy URL answers", not legal,
         "broken: " + ", ".join(legal) if legal else "all answer",
         "Claude: fix or publish the privacy page", 10)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    return [{"app": name, "folder": repo.name, "checked_at": now, "group": "Website", "step": i["id"],
             "title": i["title"], "state": i["state"], "detail": i["detail"], "how": i["how"],
             "who": who(i["id"], i["how"]), "after": "", "minutes": i["minutes"]} for i in items]


def websites() -> dict:
    config = pathlib.Path.home() / ".ship" / "config.yml"
    data = yaml.safe_load(config.read_text(encoding="utf-8")) if config.exists() else {}
    return (data or {}).get("websites") or {}


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
                "who": who(item["id"], item.get("how") or ""),
                "after": ",".join(item.get("after") or AFTER.get(item["id"], [])),
                "minutes": item.get("minutes") or MINUTES.get(item["id"], 5),
            })
        print(f"{app.name}: {report['ok']}/{report['total']}")
    only = {n for n in args.only.split(",") if n}
    for name, site in websites().items():
        if only and name not in only:
            continue
        site_rows = website_rows(name, site)
        rows += site_rows
        print(f"{name}: {sum(r['state'] == 'ok' for r in site_rows)}/{len(site_rows)}")
    pathlib.Path(args.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
