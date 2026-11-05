#!/usr/bin/env python3
"""Closing spreads and totals for a past NFL season, from The Odds API's historical odds,
to test the model and the teaser finder on more than this season's games. Run by hand
(the "Past-season odds" workflow), only on a paid plan.

Historical odds cost 10x a normal call: 20 credits per snapshot (spreads + totals, one
region). For each distinct kickoff time in the season (ESPN's schedule and finals) it takes
one snapshot ten minutes before, about 90 for a regular season, ~1,800 credits. It stops at
--max-credits, and never touches what the month needs for the core prop pulls
(scripts/odds_budget.py); run it again to continue where it stopped.
Writes data/backtests/odds-nfl-<season>.json and adds it to data/backtests/odds-index.json.

Usage: python3 scripts/odds_history.py --season 2025 [--max-credits 2000]
"""
import argparse
import json
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import books  # noqa: E402
import odds_budget  # noqa: E402
from props import odds_get, stored_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "backtests"
SCORE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2&week={week}&limit=50"
HIST = "https://api.the-odds-api.com/v4/historical/sports/americanfootball_nfl"


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs history)"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode("utf-8"))


def schedule(season):
    games = []
    for week in range(1, 19):
        try:
            d = get_json(SCORE.format(season=season, week=week))
        except Exception as e:
            print("schedule week", week, e)
            continue
        for ev in d.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
                continue
            t = {c.get("homeAway"): c for c in comp.get("competitors") or []}
            h, a = t.get("home"), t.get("away")
            if not h or not a:
                continue
            games.append({"id": str(ev.get("id")), "week": week, "date": ev.get("date"),
                          "home": (h.get("team") or {}).get("displayName"), "away": (a.get("team") or {}).get("displayName"),
                          "home_abbr": (h.get("team") or {}).get("abbreviation"), "away_abbr": (a.get("team") or {}).get("abbreviation"),
                          "hs": int(float(h.get("score") or 0)), "as": int(float(a.get("score") or 0)), "neutral": bool(comp.get("neutralSite"))})
    return games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--max-credits", type=int, default=2000)
    args = ap.parse_args()
    key = os.environ.get("ODDS_API_KEY", "").strip() or stored_key()
    budget = odds_budget.load()
    if not key or odds_budget.tier(budget) == "free":
        print("Past-season odds need a paid Odds API plan (historical odds cost 10x).")
        return 0
    DIR.mkdir(parents=True, exist_ok=True)
    out_f = DIR / f"odds-nfl-{args.season}.json"
    try:
        out = json.loads(out_f.read_text()) if out_f.exists() else {}
    except Exception:
        out = {}
    games = {g["id"]: g for g in (out.get("games") or [])}
    sched = schedule(args.season)
    for g in sched:
        games.setdefault(g["id"], g).update({k: v for k, v in g.items() if k not in ("close_spread", "close_total", "books")})
    slots = sorted({g["date"] for g in games.values() if g.get("close_spread") is None})
    print(f"{len(sched)} finished games; {len(slots)} kickoff times still to price")
    spent = 0
    for slot in slots:
        if spent + 20 > args.max_credits or not odds_budget.can_spend(budget, 20, "backfill"):
            print("stopped: credit cap or the month's spare credits")
            break
        t = datetime.fromisoformat(slot.replace("Z", "+00:00")) - timedelta(minutes=10)
        try:
            payload, hdr = odds_get("/odds", {"regions": "us", "markets": "spreads,totals", "oddsFormat": "american", "date": t.strftime("%Y-%m-%dT%H:%M:%SZ")}, key, base=HIST)
        except Exception as e:
            print(slot, "error", str(e)[:150])
            continue
        cost = int(float((hdr or {}).get("x-requests-last") or 20))
        odds_budget.record(budget, hdr, "history", cost, f"Past NFL closing lines · {args.season}")
        spent += cost
        for ev in payload.get("data") or []:
            hn, an = books.norm(ev.get("home_team")), books.norm(ev.get("away_team"))
            g = next((x for x in games.values() if x["date"] == slot and books.norm(x["home"]) == hn and books.norm(x["away"]) == an), None)
            if not g:
                continue
            sps, tots, bk = [], [], {}
            for b in ev.get("bookmakers") or []:
                row = {}
                for mk in b.get("markets") or []:
                    for oc in mk.get("outcomes") or []:
                        if mk.get("key") == "spreads" and books.norm(oc.get("name")) == hn and oc.get("point") is not None:
                            row["sp"] = float(oc["point"]); sps.append(float(oc["point"]))
                        if mk.get("key") == "totals" and str(oc.get("name")).lower() == "over" and oc.get("point") is not None:
                            row["tot"] = float(oc["point"]); tots.append(float(oc["point"]))
                if row:
                    bk[b.get("key")] = row
            if sps:
                g["close_spread"] = statistics.median(sps)
            if tots:
                g["close_total"] = statistics.median(tots)
            g["books"] = bk
    out = {"season": args.season, "league": "nfl", "source": "The Odds API historical odds, 10 minutes before kickoff",
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "credits_spent": (out.get("credits_spent") or 0) + spent,
           "games": sorted(games.values(), key=lambda g: g["date"])}
    out_f.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    idx_f = DIR / "odds-index.json"
    try:
        idx = json.loads(idx_f.read_text()) if idx_f.exists() else {}
    except Exception:
        idx = {}
    idx.setdefault("files", [])
    name = out_f.name
    if name not in idx["files"]:
        idx["files"].append(name)
    idx_f.write_text(json.dumps(idx, indent=1) + "\n")
    odds_budget.save(budget)
    priced = sum(1 for g in games.values() if g.get("close_spread") is not None)
    print(f"{priced} of {len(games)} games priced; {spent} credits this run; {budget.get('remaining')} left this month")
    return 0


if __name__ == "__main__":
    sys.exit(main())
