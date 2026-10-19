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
HIST = ROOT / "data" / "line-history.json"
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
    # A league whose feed failed this hour keeps last hour's lines instead of vanishing.
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    league_of = {str(g["id"]): g.get("league") for g in upcoming}
    for lg in LEAGUES:
        if any(league_of.get(gid) == lg for gid in out["games"]):
            continue
        kept = {gid: v for gid, v in (old.get("games") or {}).items() if league_of.get(gid) == lg}
        if kept:
            print(f"{lg}: no lines this hour; keeping {len(kept)} games from the last pull")
            out["games"].update(kept)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    record_history(out, upcoming, snap)
    return 0


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def record_history(out, upcoming, snap):
    """data/line-history.json: each game's consensus line over time, for the movement charts.
    One point per change (DraftKings' home spread, total and moneyline; the median across books
    when DraftKings has none),
    plus a point at least every 12 hours. Games drop off two days after kickoff."""
    try:
        hist = json.loads(HIST.read_text()) if HIST.exists() else {}
    except Exception:
        hist = {}
    games = hist.get("games") or {}
    now = datetime.now(timezone.utc)
    t = int(now.timestamp() // 60)  # minutes since 1970
    kick = {str(g["id"]): ts(g.get("date")) for g in snap.get("games") or []}
    for gid, books in out["games"].items():
        # DraftKings' number when it has one (the same book as the site's main line, so the
        # history doesn't jump between sources); otherwise the median across books
        dk = books.get("DraftKings") or {}
        sp = dk.get("sp") if dk.get("sp") is not None else median([b.get("sp") for b in books.values()])
        tot = dk.get("tot") if dk.get("tot") is not None else median([b.get("tot") for b in books.values()])
        dk = dk or next(iter(books.values()), {})
        row = [t, sp, tot, dk.get("mlh"), dk.get("mla")]
        pts = games.setdefault(gid, [])
        if pts and pts[-1][1:3] == row[1:3] and t - pts[-1][0] < 12 * 60:
            continue
        if pts and pts[-1][1:] == row[1:] and t - pts[-1][0] < 12 * 60:
            continue
        pts.append(row)
    cutoff = now.timestamp() - 2 * 86400
    games = {gid: pts for gid, pts in games.items() if (kick.get(gid) or 0) > cutoff}
    HIST.write_text(json.dumps({"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "fields": ["minute", "home_spread", "total", "home_ml", "away_ml"],
                                "games": games}, separators=(",", ":")) + "\n")
    save_openers(games, snap)


def save_openers(games, snap):
    """Each upcoming game's first line we saw, stored on the game ("open": {"spread",
    "total"}). The board measures line moves from this one shared number, so every visitor
    (and the published lock) sees the same board; it used to be the first line each visitor's
    own browser happened to see. Set once, never changed."""
    n = 0
    for g in snap.get("games") or []:
        if g.get("completed") or g.get("open"):
            continue
        pts = games.get(str(g.get("id"))) or []
        first = next((p for p in pts if p[1] is not None), None)
        if first:
            g["open"] = {"spread": first[1], "total": first[2], "minute": first[0]}
        elif (g.get("odds") or {}).get("home_spread") is not None:
            o = g["odds"]
            g["open"] = {"spread": o["home_spread"], "total": o.get("total"), "minute": int(datetime.now(timezone.utc).timestamp() // 60)}
        else:
            continue
        n += 1
    if n:
        SNAP.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"opening lines saved for {n} games")


if __name__ == "__main__":
    sys.exit(main())
