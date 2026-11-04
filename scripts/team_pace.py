#!/usr/bin/env python3
"""Plays per game for every finished game this season, for the totals model's pace.

Reads data/week-results.json (every finished NFL and college game on the board, with the
score) and, for each game not already saved, ESPN's box score: each team's offensive plays
(NFL: Total Plays; college, which doesn't list it: pass attempts plus rushing attempts) and
points. Writes data/team-pace.json: {"updated", "games": {id: {"league", "date", "home":
{"id", "abbr", "plays", "pts"}, "away": {...}}}}. A game ESPN can't give plays for is
retried on later runs, up to three times. Never fails the job.

Usage: python3 scripts/team_pace.py
"""
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "week-results.json"
OUT = ROOT / "data" / "team-pace.json"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/{sport}/summary?event={id}"


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs pace)"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode("utf-8"))


def plays_of(team):
    st = {s.get("name"): s.get("displayValue") for s in team.get("statistics") or []}
    try:
        if st.get("totalOffensivePlays") not in (None, ""):
            return int(float(st["totalOffensivePlays"]))
        att = int(str(st.get("completionAttempts") or "0/0").split("/")[-1] or 0)
        rush = int(float(st.get("rushingAttempts") or 0))
        return att + rush if att + rush > 0 else None
    except Exception:
        return None


def fetch(row):
    sport = "nfl" if row["league"] == "nfl" else "college-football"
    try:
        d = get_json(SUMMARY.format(sport=sport, id=row["id"]))
    except Exception as e:
        return row, None, str(e)[:120]
    teams = {t.get("homeAway"): t for t in ((d.get("boxscore") or {}).get("teams") or [])}
    h, a = teams.get("home"), teams.get("away")
    if not h or not a:
        return row, None, "no box score"
    hp, ap = plays_of(h), plays_of(a)
    if not hp or not ap:
        return row, None, "no plays"
    return row, {"league": row["league"], "date": row.get("date"),
                 "home": {"id": str(row.get("homeId")), "abbr": row.get("homeAbbr"), "plays": hp, "pts": row.get("hs")},
                 "away": {"id": str(row.get("awayId")), "abbr": row.get("awayAbbr"), "plays": ap, "pts": row.get("as")}}, None


def main():
    try:
        results = json.loads(RESULTS.read_text())
    except Exception as e:
        print("no results:", e)
        return 0
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    games = old.get("games") or {}
    tries = old.get("tries") or {}
    todo = [r for r in results if r.get("id") and r.get("hs") is not None and r.get("as") is not None
            and str(r["id"]) not in games and tries.get(str(r["id"]), 0) < 3]
    got = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for row, g, err in ex.map(fetch, todo):
            if g:
                games[str(row["id"])] = g
                got += 1
            else:
                tries[str(row["id"])] = tries.get(str(row["id"]), 0) + 1
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps({"updated": stamp, "games": games, "tries": tries}, separators=(",", ":")) + "\n")
    print(f"{len(todo)} to fetch, {got} saved, {len(games)} games in the file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
