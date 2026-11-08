#!/usr/bin/env python3
"""NFL defense tiers by stat and position (data/def-tiers.json), from nflverse's weekly player
stats: what each defense allows per game to QBs, RBs, WRs and TEs, ranked 1 (allows the least)
to 32. The play of the day and the Ladder use it to skip a prop that runs into the wrong
defense (an under against one of the 8 softest, an over against one of the 8 toughest), and
every prop shows its matchup. Free data, no Odds API calls. Runs in game-pages.yml.
Usage: python3 scripts/def_tiers.py"""
import csv, io, json, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "def-tiers.json"
URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{y}.csv"
FIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
STATS = {"rec": "receptions", "rec_yds": "receiving_yards", "rush_yds": "rushing_yards", "rush_att": "carries",
         "pass_yds": "passing_yards", "pass_td": "passing_tds", "pass_att": "attempts", "cmp": "completions", "targets": "targets"}
POS = ("QB", "RB", "WR", "TE")


def season_now():
    d = datetime.now(timezone.utc)
    return d.year if d.month >= 3 else d.year - 1


def main():
    season = season_now()
    try:
        req = urllib.request.Request(URL.format(y=season), headers={"User-Agent": "Double Gs defense tiers"})
        text = urllib.request.urlopen(req, timeout=120).read().decode("utf-8")
    except Exception as e:
        print("def tiers: download failed:", str(e)[:200])
        return 0
    allowed = defaultdict(float)
    games = defaultdict(set)
    through = 0
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("season_type") != "REG" or r.get("position") not in POS:
            continue
        d = FIX.get(r["opponent_team"], r["opponent_team"])
        w = int(r["week"])
        through = max(through, w)
        games[d].add(w)
        for k, col in STATS.items():
            try:
                allowed[(d, r["position"], k)] += float(r.get(col) or 0)
            except ValueError:
                pass
    ranks = {}
    for pos in POS:
        for k in STATS:
            per = {t: allowed[(t, pos, k)] / len(ws) for t, ws in games.items() if ws}
            order = sorted(per, key=lambda t: per[t])
            lg = sum(per.values()) / len(per) if per else 0
            for i, t in enumerate(order):
                ranks[f"{t}|{pos}|{k}"] = [i + 1, len(order), round(per[t], 2), round(lg, 2)]
    out = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "season": season, "through_week": through,
           "games": {t: len(ws) for t, ws in sorted(games.items())}, "ranks": ranks}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"def tiers: {len(games)} defenses through week {through}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
