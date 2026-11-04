#!/usr/bin/env python3
"""Real alternate spreads and totals from The Odds API, for the parlay builder, teasers and
"what would change our mind" (which otherwise estimate the price of a line off the main one).

Only on a paid plan, and only from the month's spare credits (scripts/odds_budget.py): the
first prop pull for every NFL game always comes first. Each game costs 2 credits a pull
(alternate_spreads + alternate_totals, one region). Small plan: NFL games within three days
once a day and again in the last three hours; college games within two days once a day,
soonest first, up to 30. Big plan: every 6 hours and again in the last three hours, every
college game. Writes data/alt-lines.json: {"updated", "games": {game id: {"fetched", "books":
{book: {"sp": {"home": {line: price}, "away": {...}}, "tot": {"over": {...}, "under": {...}}}}}}}.
Never fails the job.

Usage: python3 scripts/alt_lines.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import books  # noqa: E402
import odds_budget  # noqa: E402
from props import ODDS_BOOKS, odds_get, stored_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "alt-lines.json"
BASE = "https://api.the-odds-api.com/v4/sports/"
SPORT = {"nfl": "americanfootball_nfl", "cfb": "americanfootball_ncaaf"}
MARKETS = "alternate_spreads,alternate_totals"


def due(league, kick, fetched, now, tier):
    hours = (kick - now) / 3600
    age = (now - fetched) / 3600 if fetched else 1e9
    if hours < 0:
        return False
    if hours <= 3 and age >= 2:
        return True
    if tier == "big":
        return hours <= (96 if league == "nfl" else 48) and age >= 6
    return hours <= (72 if league == "nfl" else 48) and age >= 20


def parse(payload, ev):
    out = {}
    home, away = books.norm(ev.get("home_team")), books.norm(ev.get("away_team"))
    for bk in payload.get("bookmakers") or []:
        book = ODDS_BOOKS.get(bk.get("key"))
        if not book:
            continue
        b = out.setdefault(book, {"sp": {"home": {}, "away": {}}, "tot": {"over": {}, "under": {}}})
        for mk in bk.get("markets") or []:
            for oc in mk.get("outcomes") or []:
                pt, pr = oc.get("point"), oc.get("price")
                if pt is None or pr is None or abs(float(pr)) < 100:
                    continue
                key = str(float(pt))
                if mk.get("key") == "alternate_spreads":
                    nm = books.norm(oc.get("name"))
                    side = "home" if nm == home else "away" if nm == away else None
                    if side:
                        b["sp"][side][key] = int(pr)
                elif mk.get("key") == "alternate_totals":
                    side = str(oc.get("name") or "").lower()
                    if side in ("over", "under"):
                        b["tot"][side][key] = int(pr)
    return out


def main():
    key = os.environ.get("ODDS_API_KEY", "").strip() or stored_key()
    budget = odds_budget.load()
    tier = odds_budget.tier(budget)
    if key and tier == "free" and budget.get("monthly") is None:
        try:   # free call; its headers tell the plan size
            _, h = odds_get("/events", {}, key, base=BASE + SPORT["nfl"])
            odds_budget.record(budget, h, "events", 0); odds_budget.save(budget); tier = odds_budget.tier(budget)
        except Exception:
            pass
    if not key or tier == "free":
        print(f"Alternate lines: skipped ({'no key' if not key else 'free plan'})")
        return 0
    now = datetime.now(timezone.utc).timestamp()
    try:
        snap = json.loads(SNAP.read_text())
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        snap, old = {}, {}
    games = {gid: v for gid, v in (old.get("games") or {}).items()}
    board = [g for g in snap.get("games") or [] if not g.get("completed") and g.get("league") in SPORT and (books.ts(g.get("date")) or 0) > now]
    keep = {str(g["id"]) for g in board}
    games = {gid: v for gid, v in games.items() if gid in keep}
    fetched_n, spent = 0, 0
    for league in ("nfl", "cfb"):
        todo = sorted([g for g in board if g["league"] == league], key=lambda g: g.get("date") or "")
        todo = [g for g in todo if due(league, books.ts(g["date"]), books.ts((games.get(str(g["id"])) or {}).get("fetched")) if (games.get(str(g["id"])) or {}).get("fetched") else None, now, tier)]
        if league == "cfb" and tier != "big":
            todo = todo[:30]
        if not todo:
            continue
        try:
            events, hdr = odds_get("/events", {}, key, base=BASE + SPORT[league])   # free
        except Exception as e:
            print(league, "events error", str(e)[:150])
            continue
        by = {}
        for ev in events or []:
            by.setdefault((books.norm(ev.get("away_team")), books.norm(ev.get("home_team"))), []).append(ev)
        for g in todo:
            if not odds_budget.can_spend(budget, 2, "extra"):
                print("Alternate lines: stopped, the month's spare credits are spent")
                break
            kick = books.ts(g["date"])
            cands = by.get((books.norm(g["away"].get("name")), books.norm(g["home"].get("name"))), [])
            ev = next((e for e in cands if abs((books.ts(e.get("commence_time")) or 0) - kick) < 36 * 3600), None)
            if not ev:
                continue
            try:
                payload, hdr = odds_get(f"/events/{ev['id']}/odds", {"bookmakers": ",".join(ODDS_BOOKS), "markets": MARKETS, "oddsFormat": "american"}, key, base=BASE + SPORT[league])
            except Exception as e:
                print(g["id"], "error", str(e)[:150])
                continue
            cost = int(float((hdr or {}).get("x-requests-last") or 2))
            odds_budget.record(budget, hdr, "alt_lines", cost)
            odds_budget.spent_extra(budget, cost)
            spent += cost
            lines = parse(payload, ev)
            if lines:
                games[str(g["id"])] = {"fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "books": lines}
                fetched_n += 1
    odds_budget.save(budget)
    if fetched_n or set(games) != set((old.get("games") or {})):
        OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "games": games}, separators=(",", ":")) + "\n")
    print(f"Alternate lines ({tier}): {fetched_n} games fetched, {spent} credits, {len(games)} games in the file, {budget.get('remaining')} credits left")
    return 0


if __name__ == "__main__":
    sys.exit(main())
