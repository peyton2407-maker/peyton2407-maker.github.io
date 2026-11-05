#!/usr/bin/env python3
"""The Odds API credit budget, shared by every job that spends credits.

Every response carries x-requests-remaining and x-requests-used; their sum is the plan's
monthly allowance, so the jobs see an upgrade on their own with nothing to configure. The
allowance renews on the plan's reset_day each month (scripts/odds-plan.json; the 4th). data/odds-budget.json keeps the last reading and what was
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


def reset_day():
    try:
        return max(1, min(28, int(json.loads(PLAN.read_text()).get("reset_day") or 1)))
    except Exception:
        return 1


def cycle_start(now=None):
    """The day the current billing month began (the plan renews on reset_day each month)."""
    n = now or _now()
    d = reset_day()
    if n.day >= d:
        return datetime(n.year, n.month, d, tzinfo=timezone.utc)
    y, m = (n.year - 1, 12) if n.month == 1 else (n.year, n.month - 1)
    return datetime(y, m, d, tzinfo=timezone.utc)


def load():
    try:
        b = json.loads(FILE.read_text())
    except Exception:
        b = {}
    month = cycle_start().strftime("%Y-%m-%d")
    if b.get("month") == month[:7]:   # the file from before cycles started on reset_day
        b["month"] = month
    if b.get("month") != month:   # a new billing month: the allowance resets
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
    s = cycle_start(n)
    nxt = datetime(s.year + (s.month == 12), (s.month % 12) + 1, s.day, tzinfo=timezone.utc)
    return max(1.0, (nxt - n).total_seconds() / 86400)


CORE_WEEK = 95   # one core prop pull per NFL game a week (15 games x 5 markets) plus night games


def can_spend(b, cost, priority="core"):
    """The one limit is this site's own spending: never past monthly_target (13,000) in a billing
    month, counted from its own jobs only, so another project on the same key never slows it
    down or stops it. Within that: core (the first prop pull for a game) always comes first;
    extra (anything else) only from what's left after keeping the rest of the month's core
    pulls, spread over the days left (half again, so a busy NFL Sunday can borrow from quiet
    Tuesdays). The account's own floor (RESERVE credits left) is the only other stop, since
    calls past it would fail anyway."""
    rem = b.get("remaining")
    if rem is None:
        rem = monthly(b)
    spare = max(0, int(rem) - RESERVE)
    left = target(b) - own_spent(b)   # this site's own allowance left this month
    if priority == "core":
        return cost <= spare and cost <= left
    core_rest = CORE_WEEK * (days_left() / 7)
    # the pool for everything optional: this site's allowance left, after the rest of the
    # month's core pulls; paced on that alone (what the account has left only matters as the
    # floor below, so another project's use never slows the site)
    if cost > spare:
        return False
    pool = left - core_rest
    if pool <= 0:
        return False
    if priority == "backfill":
        # one-off pulls of past seasons, run by hand: the month's pool only, never the daily
        # pace the site's live pulls run on
        return cost <= pool
    day = _now().strftime("%Y-%m-%d")
    spent = b.setdefault("extra_by_day", {}).get(day, 0)
    # game days get more (props move most on Saturday and Sunday); what a quiet day leaves
    # unspent rolls into the days after, since the pace is worked out again every run
    mult = 2.2 if _now().weekday() in (5, 6) else 1.3
    return cost <= pool and spent + cost <= pool / days_left() * mult


def spent_extra(b, cost):
    day = _now().strftime("%Y-%m-%d")
    b.setdefault("extra_by_day", {})[day] = b["extra_by_day"].get(day, 0) + int(cost or 0)
