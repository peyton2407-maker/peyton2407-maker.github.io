#!/usr/bin/env python3
"""Anytime-touchdown chances for this week's NFL players (data/td-model.json).

A logistic model on what is known before kickoff: carries and targets a game over his last 6,
his share of the team's carries and targets, touchdowns a game and the share of games he
scored in this season, his team's implied points (from the spread and total), position, and a
rushing quarterback's carries. Fit on every player-game 2023-2025 with 3+ games played that
season (scripts/td-model-coef.json), then scaled on 2025 so its chances match what happened.
Tested on 2026 weeks 1-9 (never seen): players it gave 60%+ scored 62% of the time, 50-60%
51%, 40-50% 45%; its top 3 a week scored 17 of 21. The opponent's defense added nothing once
role and implied points were in, so it isn't used.
Free data (nflverse weekly stats and player ids); no Odds API calls. Runs in game-pages.yml.
Usage: python3 scripts/td_model.py"""
import csv, io, json, math, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "td-model.json"
COEF = json.loads((ROOT / "scripts" / "td-model-coef.json").read_text())
REL = "https://github.com/nflverse/nflverse-data/releases/download/"
FIX = {"LA": "LAR", "WAS": "WSH", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
fx = lambda t: FIX.get(t, t)


def get(path):
    req = urllib.request.Request(REL + path, headers={"User-Agent": "Double Gs TD model"})
    return urllib.request.urlopen(req, timeout=180).read().decode("utf-8")


def season_now():
    d = datetime.now(timezone.utc)
    return d.year if d.month >= 3 else d.year - 1


def main():
    season = season_now()
    try:
        weekly = list(csv.DictReader(io.StringIO(get(f"stats_player/stats_player_week_{season}.csv"))))
        ids = {r["gsis_id"]: r.get("espn_id") for r in csv.DictReader(io.StringIO(get("players/players.csv"))) if r.get("espn_id")}
    except Exception as e:
        print("td model: download failed:", str(e)[:200])
        return 0
    snap = json.loads((ROOT / "data" / "snapshot.json").read_text())
    now = datetime.now(timezone.utc)
    upcoming = {}
    for g in snap.get("games", []):
        if g.get("league") != "nfl" or g.get("completed"):
            continue
        o = g.get("odds") or {}
        if o.get("total") is None or o.get("home_spread") is None:
            continue
        try:
            kick = datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if (kick - now).total_seconds() < -4 * 3600 or (kick - now).days > 8:
            continue
        t, hs = float(o["total"]), float(o["home_spread"])
        home, away = g["home"]["abbr"], g["away"]["abbr"]
        hp = (t - hs) / 2
        for team, opp, pts in ((home, away, hp), (away, home, t - hp)):
            if team not in upcoming or kick < upcoming[team]["kick"]:
                upcoming[team] = {"kick": kick, "opp": opp, "imp": pts, "gid": str(g["id"])}
    rows = [r for r in weekly if r.get("season_type") == "REG" and r.get("position") in ("RB", "WR", "TE", "QB")]
    f = lambda r, k: float(r.get(k) or 0)
    tcar, ttgt = defaultdict(float), defaultdict(float)
    for r in rows:
        r["team"] = fx(r["team"]); r["w"] = int(r["week"])
        tcar[(r["team"], r["w"])] += f(r, "carries"); ttgt[(r["team"], r["w"])] += f(r, "targets")
    by = defaultdict(list)
    for r in rows:
        by[r["player_id"]].append(r)
    names, coef, b0 = COEF["names"], COEF["coef"], COEF["intercept"]
    pa, pb = COEF["platt"]
    out = {}
    for pid, L in by.items():
        L.sort(key=lambda r: r["w"])
        team = L[-1]["team"]
        up = upcoming.get(team)
        espn = ids.get(pid)
        if not up or not espn or len(L) < 3:
            continue
        mine = [r for r in L if r["team"] == team] or L
        p6 = mine[-6:]
        n = len(L)
        car5 = sum(f(r, "carries") for r in p6) / len(p6); tgt5 = sum(f(r, "targets") for r in p6) / len(p6)
        csh = sum(f(r, "carries") / max(1, tcar[(r["team"], r["w"])]) for r in p6) / len(p6)
        tsh = sum(f(r, "targets") / max(1, ttgt[(r["team"], r["w"])]) for r in p6) / len(p6)
        tds = [f(r, "rushing_tds") + f(r, "receiving_tds") for r in L]
        tdg = sum(tds) / n; tdgames = sum(1 for t in tds if t > 0) / n
        pos = L[-1]["position"]
        x = {"lcar5": math.log1p(car5), "ltgt5": math.log1p(tgt5), "csh": csh, "tsh": tsh, "tdg": tdg, "tdgames": tdgames,
             "imp": up["imp"] - 22, "dtd": 0.0, "RB": pos == "RB", "WR": pos == "WR", "TE": pos == "TE", "QB": pos == "QB",
             "RBshare*imp": (pos == "RB") * csh * (up["imp"] - 22), "QBrush": (pos == "QB") * math.log1p(car5)}
        z = b0 + sum(c * float(x[k]) for k, c in zip(names, coef))
        p = 1 / (1 + math.exp(-(pa * z + pb)))
        if p < 0.08:
            continue
        out[espn] = {"name": L[-1]["player_display_name"], "team": team, "opp": up["opp"], "pos": pos, "gid": up["gid"], "p": round(p, 4),
                     "car": round(car5, 1), "tgt": round(tgt5, 1), "csh": round(csh, 3), "tsh": round(tsh, 3), "tds": int(sum(tds)), "games": n,
                     "scored_in": int(sum(1 for t in tds if t > 0)), "imp": round(up["imp"], 1)}
    OUT.write_text(json.dumps({"at": now.strftime("%Y-%m-%dT%H:%MZ"), "season": season, "through_week": max((r["w"] for r in rows), default=0),
                               "players": out}, separators=(",", ":")))
    top = sorted(out.values(), key=lambda v: -v["p"])[:10]
    print("td model:", len(out), "players;", ", ".join(f"{v['name']} {v['p']:.2f}" for v in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
