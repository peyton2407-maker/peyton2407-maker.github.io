#!/usr/bin/env python3
"""Team logos served from this site, so they always load (no outside image server needed).

Collects every team on the board (data/snapshot.json games and ratings, data/season.json,
data/cfb-polls.json) and saves each logo once to assets/logos/<league>/<team id>.png at
128 px. Uses ESPN's version made for dark backgrounds when there is one, so navy and black
logos stay visible on the site's dark background. Writes data/logos.json, the list the
pages read: {"v": n, "nfl": {id: 1}, "cfb": {id: 1}}. Only missing logos are downloaded.
Usage: python3 scripts/logos.py
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "logos"
LIST = ROOT / "data" / "logos.json"
SIZE = 128


def load(name):
    try:
        return json.loads((ROOT / "data" / name).read_text())
    except Exception:
        return {}


def teams():
    found = {}

    def add(league, tid, url):
        if not tid or not url or "/i/teamlogos/" not in str(url):
            return
        league = "cfb" if league in ("cfb", "college-football", "ncaa") else "nfl"
        found.setdefault((league, str(tid)), url)

    snap = load("snapshot.json")
    for g in snap.get("games") or []:
        for side in ("home", "away"):
            t = g.get(side) or {}
            add(g.get("league"), t.get("id"), t.get("logo"))
    for lg, rows in (snap.get("ratings") or {}).items():
        for r in rows or []:
            add(lg, r.get("id"), r.get("logo"))
    season = load("season.json")
    for lg in ("nfl", "cfb"):
        for t in season.get(lg) or []:
            add(lg, t.get("id"), t.get("logo"))
    polls = load("cfb-polls.json")
    for poll in (polls.get("ap"), polls.get("coaches")):
        for r in ((poll or {}).get("ranks") or []) + ((poll or {}).get("others") or []):
            t = r.get("team") or {}
            logo = t.get("logo") or next((L.get("href") for L in t.get("logos") or [] if L.get("href")), None)
            add("cfb", t.get("id"), logo)
    return found


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Double Gs logos)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        body = res.read()
        if res.status != 200 or len(body) < 200 or not body.startswith(b"\x89PNG"):
            raise ValueError("not a png")
        return body


def sized(path):
    q = urllib.parse.urlencode({"img": path, "w": SIZE, "h": SIZE, "transparent": "true"})
    return "https://a.espncdn.com/combiner/i?" + q


def main():
    found = teams()
    have = load("logos.json")
    out = {"v": int(have.get("v") or 0), "nfl": dict(have.get("nfl") or {}), "cfb": dict(have.get("cfb") or {})}
    new = 0
    for (league, tid), url in sorted(found.items()):
        f = OUT / league / f"{tid}.png"
        if f.exists() and out[league].get(tid):
            continue
        path = urllib.parse.urlparse(url).path
        dark = re.sub(r"/500/", "/500-dark/", path)
        body = None
        for p in ([dark] if dark != path else []) + [path]:
            for u in (sized(p), "https://a.espncdn.com" + p):
                try:
                    body = fetch(u)
                    break
                except Exception:
                    body = None
            if body:
                break
        if not body:
            print("no logo for", league, tid, url)
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
        out[league][tid] = 1
        new += 1
        time.sleep(0.05)
    if new:
        out["v"] += 1
        LIST.write_text(json.dumps(out, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{len(found)} teams; {new} new logos; {len(out['nfl'])} NFL and {len(out['cfb'])} college saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
