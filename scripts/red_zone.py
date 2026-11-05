#!/usr/bin/env python3
"""Red-zone usage for the touchdown page: each player's carries and targets inside the 10-yard
line over his team's last 4 games, with the team's totals, from the free nflverse play-by-play
(github.com/nflverse/nflverse-data, updated nightly). Two-point tries and kneels don't count.
nflverse ids are matched to ESPN's (the site's) through nflverse's players file.
Writes data/red-zone.json: {"updated", "season", "through_week", "window",
"players": {espn id: {"team", "car10", "tgt10", "team_car10", "team_tgt10", "games"}},
"teams": {team: {"car10", "tgt10", "games", "from"}}} (a player with no touches inside the 10 isn't
listed; the page says so when his game logs show he played).
No Odds API calls. Never fails the job.

Usage: python3 scripts/red_zone.py
"""
import csv
import gzip
import io
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "red-zone.json"
BASE = "https://github.com/nflverse/nflverse-data/releases/download"
WINDOW = 4


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Double Gs red zone"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def season_now():
    d = datetime.now(timezone.utc)
    return d.year if d.month >= 3 else d.year - 1


def main():
    season = season_now()
    try:
        pbp = gzip.decompress(get(f"{BASE}/pbp/play_by_play_{season}.csv.gz")).decode("utf-8")
        players = get(f"{BASE}/players/players.csv").decode("utf-8")
    except Exception as e:
        print("red zone: download failed:", str(e)[:200])
        return 0
    espn = {}
    for row in csv.DictReader(io.StringIO(players)):
        if row.get("gsis_id") and row.get("espn_id"):
            espn[row["gsis_id"]] = row["espn_id"].split(".")[0]
    games = defaultdict(lambda: {"date": "", "car": defaultdict(int), "tgt": defaultdict(int), "tcar": 0, "ttgt": 0})   # (team, game) ->
    last_team = {}
    through = 0
    for p in csv.DictReader(io.StringIO(pbp)):
        if p.get("season_type") != "REG" or p.get("play_type") not in ("run", "pass"):
            continue
        if p.get("two_point_attempt") == "1" or p.get("qb_kneel") == "1":
            continue
        try:
            yl = float(p.get("yardline_100") or 99)
        except ValueError:
            continue
        team, gid = p.get("posteam"), p.get("game_id")
        if not team or not gid:
            continue
        through = max(through, int(float(p.get("week") or 0)))
        g = games[(team, gid)]
        g["date"] = p.get("game_date") or g["date"]
        if yl > 10:
            continue
        if p.get("rush_attempt") == "1" and p.get("rusher_player_id"):
            g["car"][p["rusher_player_id"]] += 1
            g["tcar"] += 1
            last_team[p["rusher_player_id"]] = (g["date"], team)
        elif p.get("pass_attempt") == "1" and p.get("sack") != "1" and p.get("receiver_player_id"):
            g["tgt"][p["receiver_player_id"]] += 1
            g["ttgt"] += 1
            last_team[p["receiver_player_id"]] = (g["date"], team)
    # each team's last WINDOW games
    by_team = defaultdict(list)
    for (team, gid), g in games.items():
        by_team[team].append((g["date"], gid, g))
    out, teams = {}, {}
    # nflverse team codes that differ from ESPN's (the site's)
    code = {"LA": "LAR", "WAS": "WSH"}
    for team, lst in by_team.items():
        lst.sort(key=lambda x: x[0])
        recent = lst[-WINDOW:]
        tcar = sum(g["tcar"] for _, _, g in recent)
        ttgt = sum(g["ttgt"] for _, _, g in recent)
        teams[code.get(team, team)] = {"car10": tcar, "tgt10": ttgt, "games": len(recent), "from": recent[0][0] if recent else ""}
        seen = set()
        for _, _, g in recent:
            seen.update(g["car"]); seen.update(g["tgt"])
        for pid in seen:
            if last_team.get(pid, ("", team))[1] != team or pid not in espn:
                continue
            out[espn[pid]] = {"team": code.get(team, team), "car10": sum(g["car"].get(pid, 0) for _, _, g in recent), "tgt10": sum(g["tgt"].get(pid, 0) for _, _, g in recent),
                              "team_car10": tcar, "team_tgt10": ttgt, "games": len(recent)}
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "season": season, "through_week": through,
                               "window": WINDOW, "players": out, "teams": teams}, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"red zone: {len(out)} players, through week {through}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
