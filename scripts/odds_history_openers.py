#!/usr/bin/env python3
"""Opening college totals for past seasons, to test whether the high-total under holds better
when the total hasn't risen since it opened. Run by hand (the "College opening totals"
workflow), paid plan only, from this site's optional credit pool (scripts/odds_budget.py).

One historical snapshot per week, Monday at noon Eastern, when that week's lines are up:
totals only, one region, 10 credits a snapshot, about 160 for a season. Each game keeps the
median total across books at that snapshot (games already in an earlier snapshot keep the
earlier one, the closer to the open). Writes data/backtests/cfb-open-totals.json:
{"seasons": [...], "games": [{"home", "away", "commence", "open_total", "snap"}]}.

Usage: python3 scripts/odds_history_openers.py --seasons 2021-2025 [--max-credits 1000]
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import odds_budget  # noqa: E402
from props import odds_get, stored_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "backtests" / "cfb-open-totals.json"
HIST = "https://api.the-odds-api.com/v4/historical/sports/americanfootball_ncaaf"


def mondays(season):
    d = datetime(season, 8, 24, 16, 0, tzinfo=timezone.utc)   # noon Eastern (EDT)
    while d.weekday() != 0:
        d += timedelta(days=1)
    end = datetime(season, 12, 10, tzinfo=timezone.utc)
    while d < end:
        yield d
        d += timedelta(days=7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2021-2025")
    ap.add_argument("--max-credits", type=int, default=1000)
    args = ap.parse_args()
    a, _, b = args.seasons.partition("-")
    seasons = list(range(int(a), int(b or a) + 1))
    key = os.environ.get("ODDS_API_KEY", "").strip() or stored_key()
    budget = odds_budget.load()
    if not key or odds_budget.tier(budget) == "free":
        print("Needs a paid Odds API plan (historical odds cost 10x).")
        return 0
    try:
        out = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        out = {}
    games = {(g["home"], g["away"], g["commence"][:10]): g for g in out.get("games") or []}
    done = set(out.get("snaps") or [])
    spent = 0
    for s in seasons:
        for t in mondays(s):
            snap = t.strftime("%Y-%m-%dT%H:%M:%SZ")
            if snap in done:
                continue
            if spent + 10 > args.max_credits or not odds_budget.can_spend(budget, 10, "backfill"):
                print("stopped: credit cap or the month's optional pool")
                break
            try:
                payload, hdr = odds_get("/odds", {"regions": "us", "markets": "totals", "oddsFormat": "american", "date": snap}, key, base=HIST)
            except Exception as e:
                print(snap, "error", str(e)[:150])
                continue
            cost = int(float((hdr or {}).get("x-requests-last") or 10))
            odds_budget.record(budget, hdr, "history", cost, f"Past college opening totals · {snap[:10]}")
            spent += cost
            done.add(snap)
            n = 0
            for ev in payload.get("data") or []:
                c = ev.get("commence_time") or ""
                # only this week's games (the open), not ones a week or more out
                try:
                    ct = datetime.fromisoformat(c.replace("Z", "+00:00"))
                except Exception:
                    continue
                if not (t < ct < t + timedelta(days=7)):
                    continue
                pts = [float(oc["point"]) for bk in ev.get("bookmakers") or [] for mk in bk.get("markets") or [] if mk.get("key") == "totals"
                       for oc in mk.get("outcomes") or [] if str(oc.get("name")).lower() == "over" and oc.get("point") is not None]
                if not pts:
                    continue
                k = (ev.get("home_team"), ev.get("away_team"), c[:10])
                if k in games:
                    continue
                games[k] = {"home": ev.get("home_team"), "away": ev.get("away_team"), "commence": c, "open_total": statistics.median(pts), "snap": snap}
                n += 1
            print(snap, n, "games")
    out = {"source": "The Odds API historical odds, Mondays at noon Eastern", "seasons": sorted(set(out.get("seasons") or []) | set(seasons)),
           "snaps": sorted(done), "credits_spent": (out.get("credits_spent") or 0) + spent,
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "games": sorted(games.values(), key=lambda g: g["commence"])}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    odds_budget.save(budget)
    print(f"{len(out['games'])} games with an opening total; {spent} credits this run; {budget.get('remaining')} left")
    return 0


if __name__ == "__main__":
    sys.exit(main())
