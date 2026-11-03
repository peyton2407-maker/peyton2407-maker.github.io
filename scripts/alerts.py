#!/usr/bin/env python3
"""Phone alerts when a pick locks or is graded, sent by the lock runner (scripts/lock_runner.py).

Uses ntfy (https://ntfy.sh): a free push service with phone apps for iPhone and Android, no
account needed. Install the ntfy app, add a subscription to the topic in scripts/alerts.json
(or the NTFY_TOPIC repository secret, which wins when it's set), and every lock and result
arrives on the phone with the price, the book and the bet size.

What sends an alert (only on the change, never twice):
  - an NFL or college play of the day locks, and when it's graded
  - THE LADDER locks, and when it's graded
  - this week's card locks
Never fails the lock run: a send that doesn't go through is printed and skipped.
"""
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONF = Path(__file__).with_name("alerts.json")
SITE = "https://peyton2407-maker.github.io"
ET = ZoneInfo("America/New_York")


def conf():
    try:
        c = json.loads(CONF.read_text())
    except Exception:
        c = {}
    topic = os.environ.get("NTFY_TOPIC", "").strip() or c.get("topic")
    return (c.get("server") or "https://ntfy.sh").rstrip("/"), topic


def when(iso):
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET)
        return t.strftime("%a %-I:%M %p ET")
    except Exception:
        return ""


def am(p):
    try:
        p = int(round(float(p)))
        return f"+{p}" if p > 0 else str(p)
    except Exception:
        return ""


def units(u):
    try:
        u = float(u)
    except Exception:
        return ""
    if u <= 0:
        return "Bet size: pass (the price isn't worth it)"
    return f"Bet size: {u:g}u (1u = 1% of your bankroll)"


def send(title, body, click, tags=""):
    server, topic = conf()
    if not topic:
        return
    body = "\n".join(line for line in str(body).splitlines() if line.strip()) or title
    req = urllib.request.Request(f"{server}/{topic}", data=body.encode("utf-8"), method="POST",
                                 headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Click": click, "Tags": tags, "Priority": "high"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res.read()
        print("alert sent:", title)
    except Exception as e:
        print("alert failed:", title, str(e)[:120])


def potd_rows(locks, lg):
    return {r.get("key"): r for r in ((locks.get("potd") or {}).get(lg) or []) if r and r.get("key")}


def run(old, new):
    old = old or {}
    new = new or {}
    names = {"nfl": "NFL", "cfb": "College"}
    # plays of the day
    for lg in ("nfl", "cfb"):
        before, after = potd_rows(old, lg), potd_rows(new, lg)
        for k, r in after.items():
            was = before.get(k) or {}
            page = SITE + ("/#nflpotd" if lg == "nfl" else "/#potd")
            price = f" {am(r.get('price'))}" if r.get("price") is not None else ""
            book = f" at {r.get('book')}" if r.get("book") and "standard" not in str(r.get("book")) else ""
            if r.get("locked") and not r.get("provisional") and not (was.get("locked") and not was.get("provisional")) and not r.get("result"):
                send(f"{names[lg]} play of the day locked: {r.get('line')}{price}",
                     f"{r.get('game')} · {when(r.get('kick'))}\n{r.get('line')}{price}{book}\n{units(r.get('units'))}\n{r.get('why') or ''}".strip(), page, "lock")
            if r.get("result") and not was.get("result"):
                mark = {"HIT": "white_check_mark", "MISS": "x"}.get(r.get("result"), "")
                send(f"{names[lg]} play of the day: {r.get('result')}",
                     f"{r.get('line')}{price}\n{r.get('final') or ''} {('· ' + r.get('by')) if r.get('by') else ''}".strip(), page, mark)
    # the Ladder
    b = {r.get("key"): r for r in (old.get("ladder") or []) if r}
    for r in (new.get("ladder") or []):
        if not r:
            continue
        was = b.get(r.get("key")) or {}
        legs = "\n".join(f"• {l.get('label')} {am(l.get('price'))} ({l.get('game')}, {when(l.get('kick'))})" for l in r.get("legs") or [])
        tier = " · light day, ½u" if r.get("tier") == "light" else ""
        head = f"{r.get('n')}-leg {am(r.get('american'))}" + (f" at {r.get('book')}" if r.get("book") else "") + tier
        if r.get("locked") and not was.get("locked") and not r.get("result"):
            send(f"The Ladder locked: {head}", f"{legs}\n{units(r.get('size'))}", SITE + "/#ladder", "lock")
        if r.get("result") and not was.get("result"):
            u = r.get("units")
            send(f"The Ladder: {r.get('result')}" + (f" ({'+' if (u or 0) >= 0 else ''}{u}u)" if u is not None else ""),
                 "\n".join(f"• {l.get('label')}: {l.get('result') or '—'} {('· ' + l.get('final')) if l.get('final') else ''}" for l in r.get("legs") or []),
                 SITE + "/#ladder", {"HIT": "white_check_mark", "MISS": "x"}.get(r.get("result"), ""))
    # the weekly card
    oc, nc = old.get("card") or {}, new.get("card") or {}
    if nc.get("frozen") and (not oc.get("frozen") or oc.get("weekKey") != nc.get("weekKey")):
        legs = nc.get("legs") or []
        send(f"This week's card locked: {len(legs)} plays", "\n".join(f"• {l.get('short')}: {l.get('text')}" for l in legs[:12]), SITE + "/#card", "lock")


if __name__ == "__main__":
    # python3 scripts/alerts.py --diff BEFORE.json AFTER.json   (the lock job, after its push)
    # python3 scripts/alerts.py "title" "body"                  (a test alert)
    import sys
    try:
        if len(sys.argv) >= 4 and sys.argv[1] == "--diff":
            def load(p):
                try:
                    return json.loads(Path(p).read_text())
                except Exception:
                    return {}
            run(load(sys.argv[2]), load(sys.argv[3]))
        else:
            send(sys.argv[1] if len(sys.argv) > 1 else "Double Gs test alert", sys.argv[2] if len(sys.argv) > 2 else "Alerts are working.", SITE, "bell")
    except Exception as e:   # never fail the job
        print("alerts error:", e)
