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
FACES = ROOT / "assets" / "faces" / "nfl"
FACE_LIST = ROOT / "data" / "faces.json"
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


def players():
    """NFL players the site shows: everyone with game logs (the props board) and every
    player with props in the snapshot."""
    ids = set(str(k) for k in (load("gamelogs.json").get("players") or {}))
    for g in load("snapshot.json").get("games") or []:
        if g.get("league") == "nfl":
            for pl in g.get("props") or []:
                if pl.get("id"):
                    ids.add(str(pl["id"]))
    return sorted(i for i in ids if i.isdigit())


def faces():
    have = load("faces.json")
    out = {"v": int(have.get("v") or 0), "nfl": dict(have.get("nfl") or {})}
    new = 0
    for pid in players():
        f = FACES / f"{pid}.png"
        if f.exists() and out["nfl"].get(pid):
            continue
        path = f"/i/headshots/nfl/players/full/{pid}.png"
        body = None
        for u in ("https://a.espncdn.com/combiner/i?" + urllib.parse.urlencode({"img": path, "w": 132, "h": 96, "transparent": "true"}), "https://a.espncdn.com" + path):
            try:
                body = fetch(u)
                break
            except Exception:
                body = None
        if not body:
            continue
        FACES.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
        out["nfl"][pid] = 1
        new += 1
        time.sleep(0.03)
    if new:
        out["v"] += 1
        FACE_LIST.write_text(json.dumps(out, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{new} new headshots; {len(out['nfl'])} saved")


def main():
    try:
        faces()
    except Exception as e:
        print("headshots error:", e)
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
