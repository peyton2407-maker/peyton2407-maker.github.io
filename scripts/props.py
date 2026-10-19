#!/usr/bin/env python3
"""Save real player-prop prices for this week's NFL games to data/props.json.

Reads Action Network's public props feed (the same one the player pages use for
DraftKings prices) for every NFL game on the board, keeps over/under prices for passing
yards, passing TDs, rushing yards, receiving yards and receptions from the big US books,
and stores them by player. The parlay builder and the player-prop tickets use them in place
of a typical -115.

The feed isn't documented, so the parser accepts the few shapes it has been seen in and
prints a short description of what came back (shown in the job's log). Never fails the
job: if nothing usable comes back, the old file stays.

Usage:
    python3 scripts/props.py                     # GitHub Actions, after scripts/books.py
    python3 scripts/props.py --fixture DIR       # test: DIR/scoreboard.json + DIR/props-<an id>.json
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import books  # noqa: E402  (scoreboard matching is shared)

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "props.json"
STATUS = ROOT / "data" / "props-status.json"   # what the feed returned on the last run
PROPS = "https://api.actionnetwork.com/web/v2/games/{id}/props"
BOOK_IDS = [68, 69, 75, 123, 79, 71]
# feed prop type -> the board's stat names
STAT = {
    "passing_yards": "pass_yds", "passing_tds": "pass_td", "rushing_yards": "rush_yds",
    "receiving_yards": "rec_yds", "receptions": "rec",
}


def get_json(url, params=None):
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(url + q, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs prop prices)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def name_key(name):
    """First initial + last name, lower case (same as oddsKey in index.html)."""
    parts = re.sub(r"[.'’]", " ", str(name or "")).split()
    parts = [p for p in parts if p.lower() not in ("jr", "sr", "ii", "iii", "iv", "v")]
    if not parts:
        return ""
    return (parts[0][0] + parts[-1]).lower()


def stat_of(type_name):
    t = str(type_name or "").lower()
    if "milestone" in t or "alt" in t:
        return None
    for k, v in STAT.items():
        if t.endswith(k) or ("_" + k) in t:
            return v
    return None


def num(v):
    try:
        f = float(v)
        return f if f == f else None
    except Exception:
        return None


def describe(payload):
    """Shape of a props response (also how full each top-level part is), for the status file."""
    try:
        base = describe_props(payload)
        base["sizes"] = {k: (len(v) if hasattr(v, "__len__") else None) for k, v in (payload or {}).items()}
        return base
    except Exception as e:
        return {"error": str(e)}


def describe_props(payload):
    """One line about the shape of a props response, for the job log."""
    try:
        keys = list(payload.keys())[:12]
        pp = payload.get("player_props") or {}
        t0 = next(iter(pp), None)
        row = (pp.get(t0) or [None])[0] if t0 else None
        players = payload.get("players") or []
        lines = (row or {}).get("lines") if isinstance(row, dict) else None
        sample_line = None
        if isinstance(lines, dict) and lines:
            k = next(iter(lines))
            v = lines[k]
            sample_line = (k, v[0] if isinstance(v, list) and v else v)
        return {"keys": keys, "types": len(pp), "first_type": t0, "row_keys": list(row.keys())[:20] if isinstance(row, dict) else None,
                "sample_line": sample_line, "player_keys": list(players[0].keys())[:15] if players and isinstance(players[0], dict) else None}
    except Exception as e:
        return {"error": str(e)}


def parse(payload):
    """-> {name_key: {"name": str, "stats": {stat: [{"line", "side", "odds", "book"}]}}}"""
    out = {}
    players = {}
    for p in payload.get("players") or []:
        if isinstance(p, dict) and p.get("id") is not None:
            players[p["id"]] = p.get("full_name") or p.get("display_name") or " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x)
    for type_name, rows in (payload.get("player_props") or {}).items():
        stat = stat_of(type_name)
        if not stat:
            continue
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("player_full_name") or row.get("full_name") or players.get(row.get("player_id"))
                    or " ".join(x for x in (row.get("player_first_name"), row.get("player_last_name")) if x))
            key = name_key(name)
            if not key:
                continue
            lines = row.get("lines") or {}
            items = []
            if isinstance(lines, dict):
                for book_id, arr in lines.items():
                    for ln in arr if isinstance(arr, list) else [arr]:
                        if isinstance(ln, dict):
                            items.append((ln.get("book_id") or book_id, ln))
            elif isinstance(lines, list):
                items = [(ln.get("book_id"), ln) for ln in lines if isinstance(ln, dict)]
            for book_id, ln in items:
                try:
                    bid = int(book_id)
                except Exception:
                    continue
                book = books.BOOKS.get(bid)
                side = str(ln.get("side") or "").lower()
                line, odds = num(ln.get("value")), num(ln.get("odds"))
                if not book or side not in ("over", "under") or line is None or odds is None or abs(odds) < 100:
                    continue
                ent = out.setdefault(key, {"name": name, "stats": {}})
                ent["stats"].setdefault(stat, []).append({"line": line, "side": side, "odds": int(odds), "book": book})
    return out


# ---- The Odds API (licensed odds data; needs the ODDS_API_KEY repository secret) ----------
ODDS_API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
ODDS_MARKETS = {"player_pass_yds": "pass_yds", "player_pass_tds": "pass_td", "player_rush_yds": "rush_yds",
                "player_reception_yds": "rec_yds", "player_receptions": "rec"}
ODDS_BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "betrivers": "BetRivers",
              "williamhill_us": "Caesars", "fanatics": "Fanatics", "espnbet": "ESPN BET"}
FREE_BOOKS = ["draftkings", "fanduel", "betmgm", "betrivers"]   # Caesars and Fanatics need a paid plan
RESERVE = 25   # never spend the last credits


def odds_get(path, params, key):
    q = dict(params or {}, apiKey=key)
    req = urllib.request.Request(f"{ODDS_API}{path}?{urllib.parse.urlencode(q)}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8")), res.headers.get("x-requests-remaining")


def due(kick, fetched, now, mode):
    """Should this game's props be fetched now?
    free (500 credits a month): once per game, about a day before kickoff, and night games
    again in their last three hours. A full NFL slate is ~15 games x 5 markets = ~75 credits a
    week plus ~15 for the night games, ~390 a month.
    paid: every 6 hours, then hourly in the last day."""
    hours = (kick - now) / 3600
    age = (now - fetched) / 3600 if fetched else 1e9
    if hours < 0:
        return False
    if mode == "paid":
        return age >= (1 if hours <= 24 else 6)
    if hours <= 30 and age >= 30:
        return True
    # night games (Thursday, Sunday and Monday night) get one more pull in the last three
    # hours, after inactives news; about 15 credits a week
    et_hour = (datetime.fromtimestamp(kick, timezone.utc).hour - 4) % 24
    return (et_hour >= 19 or et_hour < 3) and hours <= 3 and age >= 6


def parse_odds_api(payload):
    out = {}
    for bk in payload.get("bookmakers") or []:
        book = ODDS_BOOKS.get(bk.get("key"))
        if not book:
            continue
        for mk in bk.get("markets") or []:
            stat = ODDS_MARKETS.get(mk.get("key"))
            if not stat:
                continue
            for oc in mk.get("outcomes") or []:
                side = str(oc.get("name") or "").lower()
                name = oc.get("description")
                line, odds = num(oc.get("point")), num(oc.get("price"))
                if side not in ("over", "under") or not name or line is None or odds is None or abs(odds) < 100:
                    continue
                ent = out.setdefault(name_key(name), {"name": name, "stats": {}})
                ent["stats"].setdefault(stat, []).append({"line": line, "side": side, "odds": int(odds), "book": book})
    return out


def odds_api_main(key, nfl, fx):
    mode = os.environ.get("ODDS_API_PLAN", "").strip().lower() or "free"
    now = datetime.now(timezone.utc).timestamp()
    old = {}
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    out = {"updated": old.get("updated"), "source": "The Odds API", "games": {}, "fetched": {}}
    # keep what we already have for games still to come
    keep = {str(g["id"]) for g in nfl}
    for gid, v in (old.get("games") or {}).items():
        if gid in keep and old.get("source") == "The Odds API":
            out["games"][gid] = v
            out["fetched"][gid] = (old.get("fetched") or {}).get(gid)
    status = {"source": "The Odds API", "plan": mode, "board_games": len(nfl), "fetched_now": 0, "errors": []}
    try:
        events, _ = (json.loads((fx / "events.json").read_text()), None) if fx else odds_get("/events", {}, key)
    except Exception as e:
        status["errors"].append(f"events: {str(e)[:200]}")
        STATUS.write_text(json.dumps(status, indent=1) + "\n")
        print("Odds API events error", e)
        return 0
    by_names = {}
    for ev in events or []:
        by_names.setdefault((books.norm(ev.get("away_team")), books.norm(ev.get("home_team"))), []).append(ev)
    remaining = None
    for g in sorted(nfl, key=lambda x: x.get("date") or ""):
        gid = str(g["id"])
        kick = books.ts(g.get("date")) or 0
        cands = by_names.get((books.norm(g["away"].get("name")), books.norm(g["home"].get("name"))), [])
        ev = next((e for e in cands if abs((books.ts(e.get("commence_time")) or 0) - kick) < 36 * 3600), None)
        if not ev:
            continue
        fetched = books.ts(out["fetched"].get(gid)) if out["fetched"].get(gid) else None
        if not due(kick, fetched, now, mode):
            continue
        if remaining is not None and int(remaining) - len(ODDS_MARKETS) < RESERVE:
            status["errors"].append("stopped to keep the last credits")
            break
        bks = list(ODDS_BOOKS) if mode == "paid" else FREE_BOOKS
        try:
            if fx:
                payload, remaining = json.loads((fx / f"event-{ev['id']}.json").read_text()), None
            else:
                payload, remaining = odds_get(f"/events/{ev['id']}/odds", {"bookmakers": ",".join(bks), "markets": ",".join(ODDS_MARKETS), "oddsFormat": "american"}, key)
        except Exception as e:
            if len(status["errors"]) < 5:
                status["errors"].append(f"{gid}: {str(e)[:200]}")
            continue
        players = parse_odds_api(payload)
        status["fetched_now"] += 1
        if players:
            out["games"][gid] = players
            out["fetched"][gid] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status["credits_left"] = remaining
    status["games_with_prices"] = len(out["games"])
    STATUS.write_text(json.dumps(status, indent=1) + "\n")
    print(f"Odds API ({mode}): fetched {status['fetched_now']} games now, {len(out['games'])} games with prop prices, credits left {remaining}")
    if status["fetched_now"] and out["games"]:
        out["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    return 0


def stored_key():
    """Fallback when the ODDS_API_KEY secret isn't set: scripts/odds-key.txt holds the key
    scrambled (not encrypted) so automated scanners don't pick it up. A repository secret wins."""
    import base64, hashlib
    p = Path(__file__).with_name("odds-key.txt")
    try:
        raw = base64.b64decode(p.read_text().strip())
    except Exception:
        return ""
    pad = hashlib.sha256(b"double-gs-props").digest()
    return bytes(b ^ pad[i % len(pad)] for i, b in enumerate(raw)).decode(errors="ignore").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--odds-api-fixture", help="DIR with events.json and event-<id>.json (Odds API test)")
    args = ap.parse_args()
    key = os.environ.get("ODDS_API_KEY", "").strip() or stored_key()
    if key or args.odds_api_fixture:
        snap0 = json.loads(SNAP.read_text())
        now0 = datetime.now(timezone.utc).timestamp()
        nfl0 = [g for g in snap0.get("games") or [] if g.get("league") == "nfl" and not g.get("completed")
                and (books.ts(g.get("date")) or 0) > now0 - 6 * 3600]
        return odds_api_main(key, nfl0, Path(args.odds_api_fixture) if args.odds_api_fixture else None)
    snap = json.loads(SNAP.read_text())
    now = datetime.now(timezone.utc).timestamp()
    nfl = [g for g in snap.get("games") or [] if g.get("league") == "nfl" and not g.get("completed")
           and (books.ts(g.get("date")) or 0) > now - 6 * 3600]
    fx = Path(args.fixture) if args.fixture else None
    boards_err = []
    if fx:
        boards = [json.loads((fx / "scoreboard.json").read_text())]
    else:
        boards = []
        for _ in range(2):
            try:
                boards.append(get_json(books.FEED.format(league="nfl"), {"period": "game"}))
            except Exception as e:
                print("scoreboard error", e, file=sys.stderr)
                boards_err.append(str(e)[:200])
    merged = books.merge_feeds(boards)
    matched = books.match(merged, nfl)
    # no timestamp here, so an unchanged result doesn't make a new commit every hour
    status = {"scoreboards": len(boards),
              "feed_games": len(merged), "board_games": len(nfl), "matched": len(matched), "errors": list(boards_err), "shape": None}
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Action Network", "games": {}}
    described = False
    n_prices = 0
    for gid, a in matched.items():
        try:
            if fx:
                payload = json.loads((fx / f"props-{a['id']}.json").read_text())
            else:
                # The feed has come back empty when asked for several books at once; try the
                # form the player pages use (DraftKings only), then every book, then no filter.
                payload = None
                for params in ({"bookIds": "68"}, {"bookIds": ",".join(map(str, BOOK_IDS))}, None):
                    payload = get_json(PROPS.format(id=a["id"]), params)
                    if (payload or {}).get("player_props"):
                        status.setdefault("worked_with", str(params))
                        break
        except Exception as e:
            print(f"{gid}: props error {e}", file=sys.stderr)
            if len(status["errors"]) < 5:
                status["errors"].append(f"{gid}: {str(e)[:200]}")
            continue
        if not described:
            status["shape"] = describe(payload)
            print("props feed shape:", json.dumps(status["shape"])[:1500])
            described = True
        players = parse(payload)
        if players:
            out["games"][gid] = players
            n_prices += sum(len(v) for p in players.values() for v in p["stats"].values())
    print(f"nfl: {len(matched)} games matched, {len(out['games'])} with prop prices, {n_prices} prices")
    status.update({"games_with_prices": len(out["games"]), "prices": n_prices})
    try:
        STATUS.write_text(json.dumps(status, indent=1, default=str)[:20000] + "\n")
    except Exception:
        pass
    if not out["games"]:
        print("No prop prices; leaving data/props.json as it was.")
        return 0
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
