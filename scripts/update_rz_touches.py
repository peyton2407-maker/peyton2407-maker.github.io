#!/usr/bin/env python3
"""Rebuild goal-line and red-zone touch counts from finished NFL games.

Counts only. The anytime formula stays as it is.
A goal-line carry is a rush that starts inside the 5.
A red-zone carry or target starts inside the 20.
"""
import json
import re
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "rz-touches.json"
PAGES = [ROOT / "boom.html", ROOT / "index.html"]

SUFFIX = re.compile(r"\s+(Jr\.?|Sr\.?|II|III|IV|V)$", re.I)
ELIG = re.compile(r"^(?:(?:[A-Z]\.[A-Za-z'\-]+(?:\s+and\s+[A-Z]\.[A-Za-z'\-]+)*)\s+reported in as eligible\.\s*)+")
DIRECT = re.compile(r"^Direct snap to .+?\.\s+")
PASS_KINDS = {"Pass Reception", "Pass Incompletion", "Passing Touchdown", "Pass Interception Return"}


def season_year():
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 3 else now.year - 1


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode())


def finals(season, week):
    url = (
        "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?seasontype=2&week={week}&dates={season}&limit=50"
    )
    data = get(url)
    done = []
    any_game = False
    for ev in data.get("events") or []:
        any_game = True
        name = ((ev.get("status") or {}).get("type") or {}).get("name") or ""
        if name.startswith("STATUS_FINAL"):
            done.append(ev["id"])
    return done, any_game


def aliases(first, last):
    first = first or ""
    last = SUFFIX.sub("", last or "").strip()
    keys = set()
    letters = re.findall(r"[A-Za-z]", first)
    if not letters or not last:
        return keys
    plain_last = re.sub(r"[^A-Za-z'\-]", "", last)
    keys.add(f"{letters[0]}.{plain_last}")
    if len(letters) >= 2:
        keys.add(f"{letters[0]}.{letters[1]}.{plain_last}")
        keys.add(f"{letters[0]}{letters[1].lower()}.{plain_last}")
    parts = [p for p in re.split(r"[\s.]+", last) if p and p.lower() not in ("jr", "sr", "ii", "iii", "iv", "v")]
    if len(parts) >= 2:
        keys.add(f"{letters[0]}.{parts[0]}.{parts[-1]}")
        keys.add(f"{letters[0]}.{parts[0]}. {parts[-1]}")
        if len(letters) > 1:
            keys.add(f"{letters[0]}{letters[1].lower()}.{parts[-1]}")
    return keys


def roster(box):
    by_team = defaultdict(list)
    names = {}
    for side in box.get("players") or []:
        tid = str((side.get("team") or {}).get("id") or "")
        seen = set()
        for block in side.get("statistics") or []:
            if block.get("name") not in ("passing", "rushing", "receiving"):
                continue
            for row in block.get("athletes") or []:
                athlete = row.get("athlete") or {}
                pid = str(athlete.get("id") or "")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                names[pid] = athlete.get("displayName") or ""
                for alias in aliases(athlete.get("firstName"), athlete.get("lastName")):
                    by_team[tid].append((alias, pid))
        by_team[tid].sort(key=lambda item: -len(item[0]))
    return by_team, names


def clean(text):
    text = re.sub(r"^(?:\([^)]*\)\s*)+", "", (text or "").strip())
    text = ELIG.sub("", text)
    return DIRECT.sub("", text)


def match_start(cands, text):
    for alias, pid in cands:
        if text.startswith(alias):
            return pid
    return None


def match_target(cands, text):
    for phrase in ("intended for ", "to "):
        at = text.find(phrase)
        if at < 0:
            continue
        pid = match_start(cands, text[at + len(phrase):])
        if pid:
            return pid
    return None


def consume(eid):
    data = get(f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={eid}")
    by_team, names = roster(data.get("boxscore") or {})
    local = defaultdict(lambda: {"gl": 0, "rzc": 0, "rzt": 0, "name": ""})
    for drive in (data.get("drives") or {}).get("previous") or []:
        for play in drive.get("plays") or []:
            raw = play.get("text") or ""
            if "No Play" in raw:
                continue
            low = raw.lower()
            if "kneel" in low or "spiked" in low:
                continue
            kind = ((play.get("type") or {}).get("text") or "")
            start = play.get("start") or {}
            yte = start.get("yardsToEndzone")
            tid = str(((start.get("team") or {}).get("id")) or "")
            if yte is None or not tid or int(yte) > 20:
                continue
            yte = int(yte)
            text = clean(raw)
            cands = by_team.get(tid) or []
            if kind == "Rush":
                pid = match_start(cands, text)
                if not pid:
                    continue
                local[pid]["rzc"] += 1
                local[pid]["name"] = names.get(pid, "")
                if yte <= 5:
                    local[pid]["gl"] += 1
            elif kind in PASS_KINDS:
                pid = match_target(cands, text)
                if not pid:
                    continue
                local[pid]["rzt"] += 1
                local[pid]["name"] = names.get(pid, "")
    return local


def collect(season):
    weeks = []
    ids = []
    for week in range(1, 19):
        done, any_game = finals(season, week)
        if not any_game:
            break
        if not done:
            break
        weeks.append(week)
        ids.extend(done)
        if len(done) < 14 and week > 1:
            # A short week still in progress. Keep the finals and stop.
            break
    players = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for local in pool.map(consume, ids):
            for pid, row in local.items():
                cur = players.setdefault(pid, {"gl": 0, "rzc": 0, "rzt": 0, "name": row.get("name") or ""})
                cur["gl"] += row["gl"]
                cur["rzc"] += row["rzc"]
                cur["rzt"] += row["rzt"]
                if row.get("name"):
                    cur["name"] = row["name"]
    return weeks, players


def patch_pages(payload):
    for path in PAGES:
        text = path.read_text()
        start = text.find("window.RZ_TOUCHES = ")
        end = text.find(";\nfunction rzRow", start)
        if start < 0 or end < 0:
            raise SystemExit(f"Could not find the touch block in {path.name}")
        path.write_text(text[:start] + "window.RZ_TOUCHES = " + payload + text[end:])


def main():
    dry = "--dry-run" in sys.argv
    season = season_year()
    weeks, players = collect(season)
    if not players or not weeks:
        raise SystemExit("No finished games. Left the saved counts alone.")
    new_gl = sum(row["gl"] for row in players.values())
    old_gl = 0
    if DATA_PATH.exists():
        old = json.loads(DATA_PATH.read_text())
        old_gl = sum(row.get("gl") or 0 for row in (old.get("players") or {}).values())
    if old_gl and new_gl < old_gl:
        raise SystemExit(f"New goal-line total {new_gl} is below the saved {old_gl}. Not writing.")
    note = (
        "Goal-line carries are rushes that start inside the 5. "
        "Red-zone carries and targets start inside the 20. "
        f"Weeks {weeks[0]}-{weeks[-1]}."
    )
    payload = json.dumps(
        {"season": season, "weeks": weeks, "note": note, "players": players},
        separators=(",", ":"),
    )
    print(f"season {season} weeks {weeks[0]}-{weeks[-1]} players {len(players)} gl {new_gl} rzc {sum(r['rzc'] for r in players.values())} rzt {sum(r['rzt'] for r in players.values())}")
    if dry:
        return
    DATA_PATH.write_text(payload)
    patch_pages(payload)
    print("wrote", DATA_PATH)


if __name__ == "__main__":
    main()
