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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    args = ap.parse_args()
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
    status = {"ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "scoreboards": len(boards),
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
