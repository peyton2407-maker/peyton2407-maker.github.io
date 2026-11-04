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
PLAN = Path(__file__).with_name("odds-plan.json")
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


def keep_free():
    try:
        return int(json.loads(PLAN.read_text()).get("keep_free") or 0)
    except Exception:
        return 0


def own_spent(b):
    """What this site's jobs spent this month (another project on the same key isn't counted)."""
    return sum(int(v or 0) for v in (b.get("by_job") or {}).values())


def target(b):
    """What the jobs aim to spend this month: scripts/odds-plan.json, never more than the plan."""
    try:
        t = int(json.loads(PLAN.read_text()).get("monthly_target") or 0)
    except Exception:
        t = 0
    return min(monthly(b), t) if t > 0 else monthly(b)


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
    core_rest = CORE_WEEK * (days_left() / 7)
    # the pool for everything optional: up to the monthly target (this site's own spending),
    # never into the credits kept free for other projects, the reserve, or the rest of the
    # month's core pulls
    pool = min(spare - keep_free() - core_rest, target(b) - own_spent(b) - core_rest)
    if pool <= 0:
        return False
    day = _now().strftime("%Y-%m-%d")
    spent = b.setdefault("extra_by_day", {}).get(day, 0)
    # game days get more (props move most on Saturday and Sunday); what a quiet day leaves
    # unspent rolls into the days after, since the pace is worked out again every run
    mult = 2.2 if _now().weekday() in (5, 6) else 1.3
    return cost <= pool and spent + cost <= pool / days_left() * mult


def spent_extra(b, cost):
    day = _now().strftime("%Y-%m-%d")
    b.setdefault("extra_by_day", {})[day] = b["extra_by_day"].get(day, 0) + int(cost or 0)
