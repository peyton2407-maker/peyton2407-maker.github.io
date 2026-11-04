#!/usr/bin/env python3
"""The Odds API credit budget, shared by every job that spends credits.

Every response carries x-requests-remaining and x-requests-used; their sum is the plan's
monthly allowance, so the jobs see an upgrade on their own with nothing to configure. The
allowance resets on the 1st (UTC). data/odds-budget.json keeps the last reading and what was
spent each day, so each job can pace itself: what's left this month, minus a reserve, spread
over the days left. Order of priority when credits are short: the first prop pull for each
game, then extra prop markets and fresher prop pulls, then alternate lines; past-season
history pulls only run by hand and only from what the month can spare.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "odds-budget.json"
RESERVE = 25


def _now():
    return datetime.now(timezone.utc)


def load():
    try:
        b = json.loads(FILE.read_text())
    except Exception:
        b = {}
    month = _now().strftime("%Y-%m")
    if b.get("month") != month:   # a new month: the allowance resets
        b = {"month": month, "monthly": b.get("monthly"), "remaining": b.get("monthly"), "used": 0, "by_day": {}, "by_job": {}, "at": None}
    b.setdefault("by_day", {})
    b.setdefault("by_job", {})
    return b


def save(b):
    try:
        FILE.write_text(json.dumps(b, indent=1, sort_keys=True) + "\n")
    except Exception:
        pass


def record(b, headers, job, cost):
    """After a call: the response headers (a dict-like) and what the call cost."""
    rem = headers.get("x-requests-remaining") if headers else None
    used = headers.get("x-requests-used") if headers else None
    try:
        if rem is not None:
            b["remaining"] = int(float(rem))
        if used is not None:
            b["used"] = int(float(used))
        if rem is not None and used is not None:
            b["monthly"] = int(float(rem)) + int(float(used))
    except Exception:
        pass
    day = _now().strftime("%Y-%m-%d")
    b["by_day"][day] = b["by_day"].get(day, 0) + int(cost or 0)
    b["by_job"][job] = b["by_job"].get(job, 0) + int(cost or 0)
    b["at"] = _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def monthly(b):
    return int(b.get("monthly") or 500)


def tier(b):
    """free (the 500-credit plan), small (up to ~20K), big (more)."""
    m = monthly(b)
    return "free" if m < 2000 else "small" if m < 60000 else "big"


def days_left():
    n = _now()
    nxt = datetime(n.year + (n.month == 12), (n.month % 12) + 1, 1, tzinfo=timezone.utc)
    return max(1.0, (nxt - n).total_seconds() / 86400)


CORE_WEEK = 95   # one core prop pull per NFL game a week (15 games x 5 markets) plus night games


def can_spend(b, cost, priority="core"):
    """core: the first prop pull for a game, limited only by the reserve. extra: anything else,
    only from what's left after keeping the rest of the month's core pulls, spread over the
    days left (half again, so a busy NFL Sunday can borrow from quiet Tuesdays)."""
    rem = b.get("remaining")
    if rem is None:
        rem = monthly(b)
    spare = max(0, int(rem) - RESERVE)
    if priority == "core":
        return cost <= spare
    extra = spare - CORE_WEEK * (days_left() / 7)
    if extra <= 0:
        return False
    day = _now().strftime("%Y-%m-%d")
    spent = b.setdefault("extra_by_day", {}).get(day, 0)
    return cost <= extra and spent + cost <= extra / days_left() * 1.5


def spent_extra(b, cost):
    day = _now().strftime("%Y-%m-%d")
    b.setdefault("extra_by_day", {})[day] = b["extra_by_day"].get(day, 0) + int(cost or 0)
