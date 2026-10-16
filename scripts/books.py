#!/usr/bin/env python3
"""Save every sportsbook's lines for this week's games to data/books.json.

Reads Action Network's public scoreboard feed for the NFL and college (the same feed the
site already uses for player prop prices), keeps the regular game lines from the big US
books, and matches each game to the board by team name and kickoff. The parlay builder
reads the file to show which book has the best number and price for each leg.

The feed returns a different handful of books on each request, so it is read a few times
and merged (newest line per book wins). Never fails the job: if the feed is down, the old
file is left alone.

Usage:
    python3 scripts/books.py                        # GitHub Actions (hourly, after Refresh data)
    python3 scripts/books.py --fixture FILE.json    # test with a saved feed response
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "books.json"
FEED = "https://api.actionnetwork.com/web/v1/scoreboard/{league}"
LEAGUES = {"nfl": "nfl", "cfb": "ncaaf"}
# Action Network's ids for the books we show.
BOOKS = {68: "DraftKings", 69: "FanDuel", 75: "BetMGM", 123: "Caesars", 79: "bet365", 71: "BetRivers"}
PASSES = 3


def get_json(url, params):
    q = "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url + q, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs line check)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def norm(s):
    s = str(s or "").lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ts(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def num(v):
    try:
        f = float(v)
        return f if f == f else None
    except Exception:
        return None


def merge_feeds(payloads):
    games = {}
    for d in payloads:
        for g in (d or {}).get("games") or []:
            cur = games.setdefault(g.get("id"), dict(g, odds=[]))
            have = {(o.get("book_id"), o.get("type")): i for i, o in enumerate(cur["odds"])}
            for o in g.get("odds") or []:
                k = (o.get("book_id"), o.get("type"))
                if k not in have:
                    have[k] = len(cur["odds"])
                    cur["odds"].append(o)
                elif str(o.get("inserted") or "") > str(cur["odds"][have[k]].get("inserted") or ""):
                    cur["odds"][have[k]] = o
    return list(games.values())


def team_keys(t):
    keys = set()
    for f in ("full_name", "display_name", "location", "abbr", "short_name"):
        if t.get(f):
            keys.add(norm(t[f]))
    return keys


def board_keys(t):
    keys = set()
    for f in ("name", "location", "abbr", "short_name", "display_name"):
        if t.get(f):
            keys.add(norm(t[f]))
    return keys


def match(an_games, board_games):
    """Map board game id -> feed game (same two teams, kickoff within a day)."""
    out = {}
    for g in board_games:
        kick = ts(g.get("date"))
        hk, ak = board_keys(g.get("home") or {}), board_keys(g.get("away") or {})
        best = None
        for a in an_games:
            teams = {t.get("id"): t for t in a.get("teams") or []}
            home, away = teams.get(a.get("home_team_id")) or {}, teams.get(a.get("away_team_id")) or {}
            if not (team_keys(home) & hk and team_keys(away) & ak):
                continue
            start = ts(a.get("start_time"))
            if kick and start and abs(kick - start) > 36 * 3600:
                continue
            best = a
            break
        if best:
            out[str(g["id"])] = best
    return out


def lines_of(a):
    books = {}
    for o in a.get("odds") or []:
        name = BOOKS.get(o.get("book_id"))
        if not name or o.get("type") not in (None, "game"):
            continue
        row = {
            "sp": num(o.get("spread_home")), "sph": num(o.get("spread_home_line")), "spa": num(o.get("spread_away_line")),
            "tot": num(o.get("total")), "over": num(o.get("over")), "under": num(o.get("under")),
            "mlh": num(o.get("ml_home")), "mla": num(o.get("ml_away")), "at": o.get("inserted"),
        }
        row = {k: v for k, v in row.items() if v is not None}
        if len(row) > 1:
            books[name] = row
    return books


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="saved feed JSON: {\"nfl\": [payload...], \"cfb\": [payload...]}")
    args = ap.parse_args()
    snap = json.loads(SNAP.read_text())
    now = datetime.now(timezone.utc).timestamp()
    upcoming = [g for g in snap.get("games") or [] if not g.get("completed") and (ts(g.get("date")) or 0) > now - 6 * 3600]
    fixture = json.loads(Path(args.fixture).read_text()) if args.fixture else None
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Action Network", "games": {}}
    got_any = False
    for lg, feed_lg in LEAGUES.items():
        payloads = []
        if fixture is not None:
            payloads = fixture.get(lg) or []
        else:
            for _ in range(PASSES):
                try:
                    payloads.append(get_json(FEED.format(league=feed_lg), {"period": "game", "bookIds": ",".join(str(b) for b in BOOKS)}))
                except Exception as e:
                    print(f"{lg}: feed error {e}", file=sys.stderr)
        an = merge_feeds(payloads)
        matched = match(an, [g for g in upcoming if g.get("league") == lg])
        n_books = 0
        for gid, a in matched.items():
            books = lines_of(a)
            if books:
                out["games"][gid] = books
                n_books += len(books)
        print(f"{lg}: {len(an)} feed games, {len(matched)} matched, {n_books} book lines")
        got_any = got_any or bool(matched)
    if not got_any:
        print("No lines matched; leaving data/books.json as it was.")
        return 0
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
