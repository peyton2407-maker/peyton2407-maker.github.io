#!/usr/bin/env python3
"""Track whether The Split's college picks beat the closing line.

Win-loss records take hundreds of plays to mean anything. Closing line value (CLV) shows
skill much sooner: if the line keeps moving toward our side after we pick it, the market is
agreeing with us, and over time that is what beats the book.

For every side The Split picks, data/split-clv.json keeps:
  first   the line when The Split first made the pick (the number you could have bet)
  close   the line at kickoff (the Lock picks job's closing number, or our last look)
  clv     points the line moved toward our side from first to close (+ is good)
  ats     the result at our first number and at the close
and a summary: average CLV, how often it was positive, and the record, by week and overall.

Picks The Split later dropped stay in the log ("dropped": true), so the summary can't
only count the picks that worked out.

Runs after scripts/sync_split.py in the hourly refresh and in Build The Split.
  python3 scripts/split_clv.py              update from the current data/desk-cfb.json
  python3 scripts/split_clv.py --backfill   also replay every saved version of desk-cfb.json
                                            in git history (oldest first) to rebuild the log
"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "data" / "desk-cfb.json"
LOCKS = ROOT / "data" / "locks.json"
PAST = ROOT / "data" / "past-scorecards.json"
RESULTS = ROOT / "data" / "week-results.json"
OUT = ROOT / "data" / "split-clv.json"


def now_utc():
    return datetime.now(timezone.utc)


def when(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def num(x):
    try:
        return float(x)
    except Exception:
        return None


def side_of(team, row):
    """'home' or 'away' for a team abbreviation as The Split writes it, else None."""
    home, away = row.get("homeAbbr") or "", row.get("awayAbbr") or ""
    hit = lambda abbr: abbr and (team == abbr or abbr.startswith(team) or team.startswith(abbr))
    if hit(home) and not hit(away):
        return "home"
    if hit(away) and not hit(home):
        return "away"
    return None


def parse_line(text, row):
    """'TEX -5.5' -> ('away' or 'home', home spread). 'pick' / blank -> (None, None)."""
    parts = str(text or "").strip().split()
    if len(parts) != 2:
        return None, None
    side, n = side_of(parts[0], row), num(parts[1])
    if side is None or n is None:
        return None, None
    return side, (n if side == "home" else -n)


def observe(log, rows, seen_at):
    """Fold one look at The Split's desk (taken at seen_at) into the log."""
    for row in rows:
        gid = str(row.get("id") or "")
        kick = when(row.get("date"))
        if not gid or kick is None or seen_at >= kick:
            continue  # only lines from before kickoff count
        _, cur = parse_line(row.get("spread"), row)
        side, pick_spread = parse_line(row.get("pick"), row) if row.get("pick") not in (None, "", "NO PLAY") else (None, None)
        e = log.get(gid)
        if e is None and side is None:
            continue  # never picked: nothing to track
        if e is None:
            e = log[gid] = {
                "id": gid, "short": row.get("short") or "", "date": row.get("date"),
                "home": row.get("homeAbbr"), "away": row.get("awayAbbr"),
                "side": side, "team": row.get("homeAbbr") if side == "home" else row.get("awayAbbr"),
                "first": pick_spread, "first_pick": row.get("pick"), "first_at": iso(seen_at),
                "hours_before": round((kick - seen_at).total_seconds() / 3600, 1),
                "last": cur, "last_at": iso(seen_at), "dropped": False, "flipped": False,
            }
        if cur is not None:
            e["last"], e["last_at"] = cur, iso(seen_at)
        if side is None:
            e["dropped"] = True       # The Split no longer picks this game
        elif side != e["side"]:
            e["flipped"] = True       # The Split now likes the other side
        else:
            e["dropped"] = e["flipped"] = False


def closes():
    """Closing home spreads by game id: the Lock picks job's close first, then the scorecard."""
    out = {}
    try:
        for wk in (json.loads(PAST.read_text()).get("cfb") or {}).values():
            for r in wk:
                if num(r.get("close_spread")) is not None:
                    out[str(r["id"])] = num(r["close_spread"])
    except Exception:
        pass
    try:
        for r in json.loads(LOCKS.read_text()).get("plays") or []:
            if r.get("league") == "cfb" and num(r.get("close_spread")) is not None:
                out[str(r["id"])] = num(r["close_spread"])
    except Exception:
        pass
    return out


def finals():
    out = {}
    try:
        for r in json.loads(RESULTS.read_text()):
            if r.get("league") == "cfb" and num(r.get("hs")) is not None and num(r.get("as")) is not None:
                out[str(r["id"])] = (num(r["hs"]), num(r["as"]))
    except Exception:
        pass
    return out


def ats(side, home_spread, score):
    if home_spread is None or score is None:
        return None
    hs, as_ = score
    cover = (hs - as_) + home_spread          # > 0: home covers
    if cover == 0:
        return "P"
    return "W" if (cover > 0) == (side == "home") else "L"


def grade(log):
    cl, fin = closes(), finals()
    for e in log.values():
        # A close counts only if it really is the closing number: the Lock picks job's line
        # from near kickoff, or our own last look within 6 hours of kickoff. Early in the
        # season desk-cfb.json was saved only now and then, so "our last look" could be the
        # same early number as the pick, which would show no move at all.
        close, src = cl.get(e["id"]), "lock"
        if close is None:
            last_at, kick = when(e.get("last_at")), when(e["date"])
            close, src = (e.get("last"), "last look") if last_at and kick and (kick - last_at).total_seconds() <= 6 * 3600 else (None, None)
        e["close"], e["close_src"] = close, src
        if e.get("first") is not None and close is not None:
            moved = e["first"] - close                     # home spread fell = moved toward home
            e["clv"] = round(moved if e["side"] == "home" else -moved, 1)
        else:
            e["clv"] = None
        score = fin.get(e["id"])
        e["final"] = f"{e['away']} {int(score[1])} - {e['home']} {int(score[0])}" if score else None
        e["ats_first"] = ats(e["side"], e.get("first"), score)
        e["ats_close"] = ats(e["side"], close, score)


def week_of(e):
    # Weeks run Monday to Sunday, like The Split; the Monday date names the week.
    t = when(e["date"]).astimezone(timezone.utc)
    monday = t.toordinal() - t.weekday()
    return datetime.fromordinal(monday).strftime("%Y-%m-%d")


def summarize(rows):
    # CLV counts picks with a real closing line; the records count every pick with a final.
    rs = [r for r in rows if r.get("clv") is not None and when(r["date"]) and when(r["date"]) < now_utc()]
    def rec(key):
        w = sum(1 for r in rows if r.get(key) == "W")
        l = sum(1 for r in rows if r.get(key) == "L")
        p = sum(1 for r in rows if r.get(key) == "P")
        return {"w": w, "l": l, "p": p, "pct": round(w / (w + l), 3) if w + l else None}
    n = len(rs)
    return {
        "picks": len(rows),
        "n": n,
        "avg_clv": round(sum(r["clv"] for r in rs) / n, 2) if n else None,
        "beat_close": sum(1 for r in rs if r["clv"] > 0),
        "even": sum(1 for r in rs if r["clv"] == 0),
        "lost_close": sum(1 for r in rs if r["clv"] < 0),
        "at_first": rec("ats_first"),
        "at_close": rec("ats_close"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()

    log = {}
    if OUT.exists() and not args.backfill:
        try:
            log = {str(e["id"]): e for e in json.loads(OUT.read_text()).get("picks", [])}
        except Exception:
            log = {}

    if args.backfill:
        shas = subprocess.run(["git", "log", "--reverse", "--format=%H %cI", "--", "data/desk-cfb.json"],
                              cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
        for line in filter(None, shas):
            sha, at = line.split(" ", 1)
            try:
                rows = json.loads(subprocess.run(["git", "show", f"{sha}:data/desk-cfb.json"], cwd=ROOT,
                                                 capture_output=True, text=True, check=True).stdout)
            except Exception:
                continue
            observe(log, rows, when(at).astimezone(timezone.utc))

    observe(log, json.loads(DESK.read_text()), now_utc())
    grade(log)

    picks = sorted(log.values(), key=lambda e: (e["date"], e["id"]))
    weeks = {}
    for e in picks:
        weeks.setdefault(week_of(e), []).append(e)
    kept = [e for e in picks if not e["dropped"] and not e["flipped"]]
    data = {
        "updated": iso(now_utc()),
        "about": "Every side The Split picked: the line when first picked, the closing line, and "
                 "how many points the line moved toward our side (clv). Positive average CLV over "
                 "a season is the sign of a real edge; win-loss needs far more games.",
        "summary": {
            "all": summarize(picks),
            "kept_to_kickoff": summarize(kept),
            "by_week": {wk: summarize(rows) for wk, rows in sorted(weeks.items())},
        },
        "picks": picks,
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    s = data["summary"]["all"]
    print(f"split-clv: {len(picks)} picks tracked, {s['n']} graded, avg CLV {s['avg_clv']}, "
          f"beat close {s['beat_close']}/{s['n']}, at first number {s['at_first']}")


if __name__ == "__main__":
    main()
