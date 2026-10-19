#!/usr/bin/env python3
"""Test the NFL board's line adjustments against real results (2015-2025 regular seasons).

Downloads nflverse's game list (final scores, closing spread and total, rest days, wind) and,
for every outdoor stadium, the hour-by-hour weather that actually happened (Open-Meteo's
free archive). For each adjustment the board makes, it measures how games finished against
the closing number when the adjustment would have fired:
  - rain at kickoff (the board takes 1.1 off the total)
  - wind 15-21 and 22+ mph (0.9 and 1.6 off the total)
  - one team on a short week (1.2 toward the rested team)
  - travel of 1,200+ and 2,000+ miles (removed from the board on Oct 19)
A real edge shows up as an average miss in the same direction as the adjustment, several
standard errors from zero. Writes data/backtests/nfl.json.
Usage: python3 scripts/backtest_nfl.py
"""
import csv
import io
import json
import math
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "backtests" / "nfl.json"
GAMES = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={a}&end_date={b}&hourly=precipitation,wind_speed_10m&wind_speed_unit=mph&precipitation_unit=inch&timezone=GMT"
ET = ZoneInfo("America/New_York")
LL = {"ARI": (33.53, -112.26), "ATL": (33.76, -84.40), "BAL": (39.28, -76.62), "BUF": (42.77, -78.79), "CAR": (35.23, -80.85),
      "CHI": (41.86, -87.62), "CIN": (39.10, -84.52), "CLE": (41.51, -81.70), "DAL": (32.75, -97.09), "DEN": (39.74, -105.02),
      "DET": (42.34, -83.05), "GB": (44.50, -88.06), "HOU": (29.68, -95.41), "IND": (39.76, -86.16), "JAX": (30.32, -81.64),
      "KC": (39.05, -94.48), "LV": (36.09, -115.18), "LAC": (33.95, -118.34), "LA": (33.95, -118.34), "MIA": (25.96, -80.24),
      "MIN": (44.97, -93.26), "NE": (42.09, -71.26), "NO": (29.95, -90.08), "NYG": (40.81, -74.07), "NYJ": (40.81, -74.07),
      "PHI": (39.90, -75.17), "PIT": (40.45, -80.02), "SF": (37.40, -121.97), "SEA": (47.60, -122.33), "TB": (27.98, -82.50),
      "TEN": (36.17, -86.77), "WAS": (38.91, -76.86), "OAK": (37.75, -122.20), "SD": (32.78, -117.12), "STL": (38.63, -90.19)}


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Double Gs backtest)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def stat(xs):
    n = len(xs)
    if n < 3:
        return {"n": n}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return {"n": n, "mean": round(m, 2), "t": round(m / (sd / math.sqrt(n)), 2)}


def miles(a, b):
    (la1, lo1), (la2, lo2) = LL[a], LL[b]
    p = math.pi / 180
    d = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 3959 * 2 * math.asin(math.sqrt(d))


def main():
    rows = [r for r in csv.DictReader(io.StringIO(get(GAMES).decode("utf-8")))
            if r["game_type"] == "REG" and r["result"] and r["spread_line"] and r["total_line"] and 2015 <= int(r["season"]) <= 2025]
    print(len(rows), "games")
    outdoor = [r for r in rows if r["roof"] in ("outdoors", "open") and r["location"] == "Home" and r["home_team"] in LL]
    # actual weather at each home stadium, one archive pull per team
    wx = {}
    for team in sorted({r["home_team"] for r in outdoor}):
        lat, lon = LL[team]
        try:
            j = json.loads(get(ARCHIVE.format(lat=lat, lon=lon, a="2015-09-01", b="2026-01-15")))
            h = j["hourly"]
            wx[team] = {t: (p, w) for t, p, w in zip(h["time"], h["precipitation"], h["wind_speed_10m"])}
            print(team, len(wx[team]), "hours")
        except Exception as e:
            print(team, "weather error", e)
        time.sleep(1)
    res = defaultdict(list)
    for r in outdoor:
        hw = wx.get(r["home_team"])
        if not hw:
            continue
        try:
            kick = datetime.strptime(r["gameday"] + " " + r["gametime"], "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(timezone.utc)
        except Exception:
            continue
        hours = [(kick + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(0, 4)]
        vals = [hw.get(h) for h in hours if hw.get(h)]
        if not vals:
            continue
        rain = sum(v[0] or 0 for v in vals)
        wind = max(v[1] or 0 for v in vals[:2])
        te = float(r["total"]) - float(r["total_line"])
        res["all outdoor"].append(te)
        res["rain 0.08in+ over the game" if rain >= 0.08 else "dry"].append(te)
        res["wind 22+ mph" if wind >= 22 else "wind 15-21 mph" if wind >= 15 else "wind under 15"].append(te)
    side = defaultdict(list)
    for r in rows:
        e = float(r["result"]) - float(r["spread_line"])
        try:
            hr, ar = float(r["home_rest"]), float(r["away_rest"])
            if hr <= 4.6 < ar:
                side["home on a short week (board: 1.2 to the visitor)"].append(-e)
            elif ar <= 4.6 < hr:
                side["visitor on a short week (board: 1.2 to home)"].append(e)
        except Exception:
            pass
        if r["location"] == "Home" and r["home_team"] in LL and r["away_team"] in LL:
            mi = miles(r["away_team"], r["home_team"])
            side["visitor flew 2,000+ miles" if mi >= 2000 else "visitor flew 1,200-2,000 miles" if mi >= 1200 else "visitor under 1,200 miles"].append(e)
    report = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "about": "2015-2025 NFL regular season. Totals: final total minus closing total at outdoor home stadiums, "
                       "by the weather that actually happened in the first hours of the game. Sides: final margin minus "
                       "closing spread, signed toward the side the board's adjustment favors.",
              "totals_by_weather": {k: stat(v) for k, v in res.items()},
              "sides": {k: stat(v) for k, v in side.items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
