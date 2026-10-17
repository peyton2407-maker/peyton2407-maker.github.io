#!/usr/bin/env python3
"""Build The Split (split/index.html) for the current college week, from ESPN.

Every run (daily, see .github/workflows/build-split.yml):
  1. Pulls the week's FBS scoreboard (games, DraftKings lines, records, ranks, leaders),
     ESPN's power index (FPI, strength of record, schedule, efficiencies) and every FBS
     team's season stats, own and allowed, in one league-wide request.
  2. Builds each game's sheet: power and résumé, each offense against the other defense,
     both offenses' profile, and the season rails, every number ranked across FBS.
  3. Projects a score for each game and makes the desk's picks:
       - stats matchup: each offense's points a game against what the other defense allows,
         plus 2.5 points to the home team
       - power rating: the FPI gap plus 2.5 to the home team
       - the projection starts at the market's own number and moves 35% of the way toward
         the blend of those two. A side is picked only when BOTH the stats matchup and FPI
         are 3+ points off the line in the same direction; a total only when the stats total
         is 6+ points off. (This season, FPI alone against the line went 10-19 at 3+
         points, so neither signal is trusted on its own.)
     A game within two hours of kickoff, or already played, keeps the desk row it had, so
     a pick never changes once it can be locked. Desk rows made by hand (no "model" tag)
     are kept for the week they were made.
  4. Runs The Split's own play-by-play grading (refreshPlays) in headless Chromium and saves
     split/advanced.json, so visitors don't each download every game of the season.
Then scripts/sync_split.py copies the desk and matchup notes to the main site.

Usage: python3 scripts/build_split.py [--week N] [--no-plays]
"""
import argparse
import asyncio
import json
import math
import mimetypes
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "split" / "index.html"
ADV = ROOT / "split" / "advanced.json"
POLLS = ROOT / "data" / "cfb-polls.json"
ET = ZoneInfo("America/New_York")
SEASON = 2026
SEASON_OPEN = datetime(2026, 9, 1, 12, 0, tzinfo=ET)  # weeks start Tuesdays, like the site
SITE = "https://peyton2407-maker.github.io"
SB = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?week={w}&seasontype=2&groups=80&limit=300"
FPI = "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?limit=150"
STATS = ("https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/statistics/byteam?region=us&lang=en"
         "&contentorigin=espn&isqualified=true&page=1&limit=200&category=offense&season={s}&seasontype=2&groups=80")
HFA = 2.5
SIGMA = 15.25
PULL = 0.35          # how far the desk moves from the market toward our blend
SIDE_GAP = 3.0       # stats matchup and FPI must each be this far off the line, same way
TOTAL_GAP = 6.0      # stats total this far off the posted total
MODEL = "dg-split-1"


def get_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs Split)"})
            with urllib.request.urlopen(req, timeout=45) as res:
                return json.loads(res.read().decode("utf-8"))
        except Exception as e:
            last = e
    raise last


def current_week(now=None):
    """Same clock as the site: weeks start Tuesday; Monday from 6 AM ET belongs to the next."""
    now = (now or datetime.now(timezone.utc)).astimezone(ET)
    days = (now.date() - SEASON_OPEN.date()).days
    w = max(1, days // 7 + 1)
    if now.weekday() == 0 and now.hour >= 6:
        w += 1
    return w


# ---------------------------------------------------------------------------------------------
# league-wide stats
def parse_stats(payload):
    """team id -> {"own": {name: value}, "opp": {name: value}} for every FBS team."""
    cats = {c["name"]: c["names"] for c in payload.get("categories") or []}
    out = {}
    for t in payload.get("teams") or []:
        tid = str(t["team"]["id"])
        own, opp = {}, {}
        for c in t.get("categories") or []:
            names = cats.get(c.get("name")) or []
            bag = opp if str(c.get("splitId")) == "900" else own
            for n, v in zip(names, c.get("values") or []):
                if n not in bag:
                    bag[n] = v
        out[tid] = {"own": own, "opp": opp}
    return out


def safe(n, d):
    try:
        return n / d if d else None
    except Exception:
        return None


def team_metrics(s):
    O, P = s["own"], s["opp"]
    gp = O.get("gamesPlayed") or 0
    if not gp:
        return None
    pa, ra = O.get("passingAttempts") or 0, O.get("rushingAttempts") or 0
    plays = pa + ra
    give = (O.get("interceptions") or 0) + (P.get("fumblesRecovered") or 0)
    take = (P.get("interceptions") or 0) + (O.get("fumblesRecovered") or 0)
    ppg = O.get("totalPointsPerGame")
    m = {
        "off_ppg": ppg, "def_ppg": P.get("totalPointsPerGame"),
        "off_ypg": O.get("yardsPerGame"), "def_ypg": P.get("yardsPerGame"),
        "off_pass": O.get("passingYardsPerGame"), "def_pass": P.get("passingYardsPerGame"),
        "off_rush": O.get("rushingYardsPerGame"), "def_rush": P.get("rushingYardsPerGame"),
        "sacks_taken": safe(O.get("sacks") or 0, gp), "sacks_made": safe(P.get("sacks") or 0, gp),
        "give_pg": safe(give, gp), "take_pg": safe(take, gp),
        "ypa": O.get("yardsPerPassAttempt"), "ypr": O.get("yardsPerRushAttempt"),
        "pass_rate": safe(pa, plays), "rush_rate": safe(ra, plays),
        "qbr": O.get("QBRating"), "int_pct": safe(O.get("interceptions") or 0, pa),
        "fum_rush": safe(P.get("fumblesRecovered") or 0, ra),
        "third_pct": O.get("thirdDownConvPct"), "third_att": safe(O.get("thirdDownAttempts") or 0, gp),
        "fourth_pct": O.get("fourthDownConvPct"), "fourth_att": safe(O.get("fourthDownAttempts") or 0, gp),
        "td_pg": safe((O.get("passingTouchdowns") or 0) + (O.get("rushingTouchdowns") or 0), gp),
        "plays_pg": safe(plays, gp), "pts_play": safe(ppg, safe(plays, gp)),
        "margin": (ppg - P.get("totalPointsPerGame")) if ppg is not None and P.get("totalPointsPerGame") is not None else None,
        "to_margin": take - give,
        "pen_pg": safe(O.get("totalPenalties") or 0, gp), "pen_ypg": safe(O.get("totalPenaltyYards") or 0, gp),
        "fd_pen": safe(O.get("firstDownsPenalty") or 0, gp),
        "fg_pct": O.get("fieldGoalPct"), "net_punt": O.get("netAvgPuntYards"),
    }
    # ESPN reports some percentages as 0-100 already
    return m


# metric -> True when a bigger number is better (rank 1 = biggest); "flat" ranks most to least
BETTER_HIGH = {
    "off_ppg": True, "def_ppg": False, "off_ypg": True, "def_ypg": False, "off_pass": True, "def_pass": False,
    "off_rush": True, "def_rush": False, "sacks_taken": False, "sacks_made": True, "give_pg": False, "take_pg": True,
    "ypa": True, "ypr": True, "pass_rate": "flat", "rush_rate": "flat", "qbr": True, "int_pct": False, "fum_rush": False,
    "third_pct": True, "third_att": "flat", "fourth_pct": True, "fourth_att": "flat", "td_pg": True, "plays_pg": "flat",
    "pts_play": True, "margin": True, "to_margin": True, "pen_pg": False, "pen_ypg": False, "fd_pen": "flat",
    "fg_pct": True, "net_punt": True,
}


def rank_all(metrics):
    ranks = {tid: {} for tid in metrics}
    for key, hi in BETTER_HIGH.items():
        vals = [(tid, m[key]) for tid, m in metrics.items() if m and m.get(key) is not None]
        vals.sort(key=lambda x: -x[1] if hi in (True, "flat") else x[1])
        prev, r = None, 0
        for i, (tid, v) in enumerate(vals):
            if v != prev:
                r = i + 1
                prev = v
            ranks[tid][key] = r
    return ranks


def f1(v, d=1):
    return "—" if v is None else f"{v:.{d}f}"


def pct(v, already100=False, d=1):
    if v is None:
        return "—"
    return f"{(v if already100 else v * 100):.{d}f}%"


def cell(text, rank, caption, flat=False):
    c = {"text": text, "rank": rank, "caption": caption}
    if flat:
        c["flatRank"] = True
    return c


# ---------------------------------------------------------------------------------------------
def parse_fpi(payload):
    cats = {c["name"]: c["names"] for c in payload.get("categories") or []}
    out = {}
    for t in payload.get("teams") or []:
        tid = str(t["team"]["id"])
        row = {}
        for c in t.get("categories") or []:
            for n, v in zip(cats.get(c.get("name")) or [], c.get("values") or []):
                row.setdefault(c["name"] + "." + n, v)
        out[tid] = row
    return out


def poll_ranks():
    try:
        d = json.loads(POLLS.read_text())
        return {str(r["team"]["id"]): r.get("current") for r in (d.get("ap") or {}).get("ranks") or [] if r.get("team")}
    except Exception:
        return {}


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def num(v):
    try:
        return float(str(v).replace("+", "").replace("o", "").replace("u", ""))
    except Exception:
        return None


def fav_label(home, away, home_margin):
    """'UGA -19.7' from the home team's projected margin."""
    if home_margin is None:
        return ""
    if abs(home_margin) < 0.05:
        return "Pick 'em"
    return f"{home} -{abs(home_margin):.1f}" if home_margin > 0 else f"{away} -{abs(home_margin):.1f}"


def line_txt(x):
    if x is None:
        return ""
    s = f"{x:+.1f}"
    return s[:-2] if s.endswith(".0") and False else s


# ---------------------------------------------------------------------------------------------
def team_dict(c, fbs, ap):
    t = c["team"]
    rec = {r.get("type"): r.get("summary") for r in c.get("records") or []}
    cur = (c.get("curatedRank") or {}).get("current")
    rank = ap.get(str(t["id"])) or (cur if cur and cur <= 25 else None)
    logo = t.get("logo") or ""
    return {
        "id": str(t["id"]), "abbrev": t.get("abbreviation") or "", "name": t.get("displayName") or "",
        "location": t.get("location") or "", "color": t.get("color") or "343c2e", "logo": logo,
        "rank": rank, "record": rec.get("total") or "", "confRecord": rec.get("vsconf") or "",
        "conference": "", "level": "FBS" if str(t["id"]) in fbs else "FCS",
    }


def leaders(c):
    roles = {"passingLeader": "Pass", "rushingLeader": "Rush", "receivingLeader": "Recv"}
    out = []
    for L in c.get("leaders") or []:
        role = roles.get(L.get("name"))
        top = (L.get("leaders") or [None])[0]
        if role and top:
            who = (top.get("athlete") or {}).get("shortName") or ""
            out.append({"role": role, "line": f"{who} · {top.get('displayValue') or ''}".strip()})
    return out


def when_et(iso, valid=True):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    day = d.strftime("%a, %b ") + str(d.day)
    return day + (", " + d.strftime("%I:%M %p").lstrip("0") if valid is not False else ", time TBD")


def build(week, old):
    print(f"Building The Split for college week {week}")
    board = get_json(SB.format(w=week))
    fpi = parse_fpi(get_json(FPI))
    stats = parse_stats(get_json(STATS.format(s=SEASON)))
    metrics = {tid: team_metrics(s) for tid, s in stats.items()}
    metrics = {tid: m for tid, m in metrics.items() if m}
    ranks = rank_all(metrics)
    fbs = set(metrics) | set(fpi)
    ap = poll_ranks()
    print(f"  {len(board.get('events') or [])} games, FPI for {len(fpi)} teams, stats for {len(metrics)} teams")

    tmpl = {}
    for sh in (old.get("sheets") or {}).values():
        for sec in sh.get("sections") or []:
            tmpl.setdefault(sec["id"], sec)
        if len(tmpl) >= 5:
            break
    note = lambda sid, default: (tmpl.get(sid) or {}).get("note") or default
    old_desk = {str(r["id"]): r for r in old.get("desk") or []}
    now = datetime.now(timezone.utc)

    slate, sheets, desk = [], {}, []
    for ev in board.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        if "home" not in cs or "away" not in cs:
            continue
        H, A = cs["home"], cs["away"]
        home, away = team_dict(H, fbs, ap), team_dict(A, fbs, ap)
        gid = str(ev["id"])
        state = ((comp.get("status") or {}).get("type") or {}).get("state") or "pre"
        neutral = bool(comp.get("neutralSite"))
        odds = (comp.get("odds") or [{}])[0] if comp.get("odds") else {}
        spread = num(odds.get("spread")) if odds else None          # home line
        total = num(odds.get("overUnder")) if odds else None
        ps, tt, ml = odds.get("pointSpread") or {}, odds.get("total") or {}, odds.get("moneyline") or {}
        price = lambda node, side: ((node.get(side) or {}).get("close") or {}).get("odds")
        hf, af = (fpi.get(home["id"]) or {}).get("fpi.fpi"), (fpi.get(away["id"]) or {}).get("fpi.fpi")
        fm = (hf - af + (0 if neutral else HFA)) if hf is not None and af is not None else None
        mm = -spread if spread is not None else None
        base_total = total if total is not None else 55.0

        line = {
            "marketSpread": odds.get("details") or "—", "spreadPrice": f"{price(ps, 'away') or '—'} / {price(ps, 'home') or '—'}",
            "total": f1(total) if total is not None else "—",
            "overPrice": "o" + (price(tt, "over") or "—"), "underPrice": "u" + (price(tt, "under") or "—"),
            "awayMl": price(ml, "away") or "—", "homeMl": price(ml, "home") or "—",
            "marketAway": f1((total - mm) / 2) if total is not None and mm is not None else "—",
            "marketHome": f1((total + mm) / 2) if total is not None and mm is not None else "—",
            "fpiSpread": fav_label(home["abbrev"], away["abbrev"], fm) or "—",
            "fpiNote": "FPI gap on a neutral field." if neutral else "FPI gap, then 2.5 points to the home team.",
            "fpiAway": f1((base_total - fm) / 2) if fm is not None else "—",
            "fpiHome": f1((base_total + fm) / 2) if fm is not None else "—",
            "awayWin": f"{round((1 - ncdf(fm / SIGMA)) * 100)}%" if fm is not None else "—",
            "homeWin": f"{round(ncdf(fm / SIGMA) * 100)}%" if fm is not None else "—",
        }
        scores = {k: (cs[k].get("score") if state != "pre" else None) for k in ("away", "home")}
        venue = comp.get("venue") or {}
        tv = " / ".join(n for b in comp.get("broadcasts") or [] for n in b.get("names") or [])
        tvalid = comp.get("timeValid", True)
        slate.append({"id": gid, "when": when_et(ev["date"], tvalid), "tv": tv, "state": state,
                      "spread": odds.get("details") or "", "total": f1(total) if total is not None else "",
                      "fpiLean": line["fpiSpread"] if fm is not None else "", "away": away, "home": home,
                      "awayScore": scores["away"], "homeScore": scores["home"]})

        # ---- the sheet
        fa, fh = fpi.get(away["id"]) or {}, fpi.get(home["id"]) or {}
        ma, mh = metrics.get(away["id"]) or {}, metrics.get(home["id"]) or {}
        ra, rh = ranks.get(away["id"]) or {}, ranks.get(home["id"]) or {}

        def fcell(f, key, rank_key, cap, fmt=lambda v: f1(v)):
            v = f.get(key)
            r = f.get(rank_key)
            return cell(fmt(v) if v is not None else "—", int(r) if r else None, cap)

        def rcell(f, rank_key, cap):
            r = f.get(rank_key)
            return cell(str(int(r)) if r else "—", int(r) if r else None, cap)

        aa, ha = away["abbrev"], home["abbrev"]
        power = [
            {"id": "power-rating", "left": fcell(fa, "fpi.fpi", "fpi.fpirank", aa), "right": fcell(fh, "fpi.fpi", "fpi.fpirank", ha)},
            {"id": "poll-rank", "left": cell(f"#{away['rank']}" if away["rank"] else "NR", None, aa), "right": cell(f"#{home['rank']}" if home["rank"] else "NR", None, ha)},
            {"id": "strength-of-record", "left": rcell(fa, "resume.accomplishmentrank", aa), "right": rcell(fh, "resume.accomplishmentrank", ha)},
            {"id": "current-sos", "left": rcell(fa, "resume.avgsosrank", aa), "right": rcell(fh, "resume.avgsosrank", ha)},
            {"id": "remaining-sos", "left": rcell(fa, "resume.sosremainingrank", aa), "right": rcell(fh, "resume.sosremainingrank", ha)},
            {"id": "game-control", "left": rcell(fa, "resume.gamecontrolrank", aa), "right": rcell(fh, "resume.gamecontrolrank", ha)},
            {"id": "off-efficiency", "left": fcell(fa, "efficiencies.offefficiency", "efficiencies.offefficiencyrank", aa), "right": fcell(fh, "efficiencies.offefficiency", "efficiencies.offefficiencyrank", ha)},
            {"id": "def-efficiency", "left": fcell(fa, "efficiencies.defefficiency", "efficiencies.defefficiencyrank", aa), "right": fcell(fh, "efficiencies.defefficiency", "efficiencies.defefficiencyrank", ha)},
            {"id": "st-efficiency", "left": fcell(fa, "efficiencies.stefficiency", "efficiencies.stefficiencyrank", aa), "right": fcell(fh, "efficiencies.stefficiency", "efficiencies.stefficiencyrank", ha)},
        ]

        def mc(m, r, key, cap, fmt=f1, flat=False):
            v = m.get(key)
            return cell(fmt(v) if v is not None else "—", r.get(key), cap, flat)

        def vs(om, orr, dm, drr, ab):
            return [
                {"id": "off-ppg", "left": mc(om, orr, "off_ppg", f"{ab} scores"), "right": mc(dm, drr, "def_ppg", "allowed")},
                {"id": "off-ypg", "left": mc(om, orr, "off_ypg", f"{ab} offense"), "right": mc(dm, drr, "def_ypg", "allowed")},
                {"id": "off-pass-ypg", "left": mc(om, orr, "off_pass", f"{ab} pass"), "right": mc(dm, drr, "def_pass", "allowed")},
                {"id": "off-rush-ypg", "left": mc(om, orr, "off_rush", f"{ab} rush"), "right": mc(dm, drr, "def_rush", "allowed")},
                {"id": "sacks", "left": mc(om, orr, "sacks_taken", f"{ab} taken / g"), "right": mc(dm, drr, "sacks_made", "sacks / g")},
                {"id": "ball-security", "left": mc(om, orr, "give_pg", f"{ab} giveaways"), "right": mc(dm, drr, "take_pg", "takeaways")},
            ]

        p100 = lambda v: pct(v, already100=True)
        profile = [
            {"id": "yds-attempt", "left": mc(ma, ra, "ypa", aa), "right": mc(mh, rh, "ypa", ha)},
            {"id": "yds-rush", "left": mc(ma, ra, "ypr", aa), "right": mc(mh, rh, "ypr", ha)},
            {"id": "pass-rate", "left": mc(ma, ra, "pass_rate", aa, pct, True), "right": mc(mh, rh, "pass_rate", ha, pct, True)},
            {"id": "rush-rate", "left": mc(ma, ra, "rush_rate", aa, pct, True), "right": mc(mh, rh, "rush_rate", ha, pct, True)},
            {"id": "qbr", "left": mc(ma, ra, "qbr", aa), "right": mc(mh, rh, "qbr", ha)},
            {"id": "ints-per-pass", "left": mc(ma, ra, "int_pct", aa, pct), "right": mc(mh, rh, "int_pct", ha, pct)},
            {"id": "fumbles-lost-per-rush", "left": mc(ma, ra, "fum_rush", aa, lambda v: f"{v:.3f}"), "right": mc(mh, rh, "fum_rush", ha, lambda v: f"{v:.3f}")},
            {"id": "third-down-pct", "left": mc(ma, ra, "third_pct", aa, p100), "right": mc(mh, rh, "third_pct", ha, p100)},
            {"id": "third-down-att", "left": mc(ma, ra, "third_att", aa, f1, True), "right": mc(mh, rh, "third_att", ha, f1, True)},
            {"id": "fourth-down-pct", "left": mc(ma, ra, "fourth_pct", aa, p100), "right": mc(mh, rh, "fourth_pct", ha, p100)},
            {"id": "fourth-down-att", "left": mc(ma, ra, "fourth_att", aa, f1, True), "right": mc(mh, rh, "fourth_att", ha, f1, True)},
            {"id": "off-td-per-game", "left": mc(ma, ra, "td_pg", aa), "right": mc(mh, rh, "td_pg", ha)},
            {"id": "plays-off", "left": mc(ma, ra, "plays_pg", aa, f1, True), "right": mc(mh, rh, "plays_pg", ha, f1, True)},
            {"id": "pace", "left": cell("—", None, aa), "right": cell("—", None, ha)},
            {"id": "pts-per-play-off", "left": mc(ma, ra, "pts_play", aa, lambda v: f"{v:.2f}"), "right": mc(mh, rh, "pts_play", ha, lambda v: f"{v:.2f}")},
        ]
        sgn = lambda v: f"{v:+.1f}"
        rails = [
            {"id": "off-ppg", "left": mc(ma, ra, "off_ppg", f"{aa} scores"), "right": mc(mh, rh, "off_ppg", f"{ha} scores")},
            {"id": "def-ppg", "left": mc(ma, ra, "def_ppg", f"{aa} allows"), "right": mc(mh, rh, "def_ppg", f"{ha} allows")},
            {"id": "ppg-margin", "left": mc(ma, ra, "margin", aa, sgn), "right": mc(mh, rh, "margin", ha, sgn)},
            {"id": "turnover-margin", "left": mc(ma, ra, "to_margin", f"{aa} season", lambda v: str(int(v))), "right": mc(mh, rh, "to_margin", f"{ha} season", lambda v: str(int(v)))},
            {"id": "giveaways", "left": mc(ma, ra, "give_pg", aa), "right": mc(mh, rh, "give_pg", ha)},
            {"id": "takeaways", "left": mc(ma, ra, "take_pg", aa), "right": mc(mh, rh, "take_pg", ha)},
            {"id": "penalties", "left": mc(ma, ra, "pen_pg", aa), "right": mc(mh, rh, "pen_pg", ha)},
            {"id": "penalty-ypg", "left": mc(ma, ra, "pen_ypg", aa), "right": mc(mh, rh, "pen_ypg", ha)},
            {"id": "fd-by-penalty", "left": mc(ma, ra, "fd_pen", aa, f1, True), "right": mc(mh, rh, "fd_pen", ha, f1, True)},
            {"id": "stuffs", "left": cell("—", None, f"{aa} defense"), "right": cell("—", None, f"{ha} defense")},
            {"id": "field-goal-pct", "left": mc(ma, ra, "fg_pct", aa, p100), "right": mc(mh, rh, "fg_pct", ha, p100)},
            {"id": "net-punt", "left": mc(ma, ra, "net_punt", aa), "right": mc(mh, rh, "net_punt", ha)},
        ]
        sections = [
            {"id": "power", "title": "Power and résumé", "note": note("power", "Green is a national rank near the top. Rank 1 is best."), "rows": power},
            {"id": "away-off", "title": f"{aa} offense vs {ha} defense", "note": note("away-off", "Left is what this offense has done. Right is what that defense has allowed."), "rows": vs(ma, ra, mh, rh, aa)},
            {"id": "home-off", "title": f"{ha} offense vs {aa} defense", "note": note("home-off", "Same read, other direction."), "rows": vs(mh, rh, ma, ra, ha)},
            {"id": "profile", "title": "Both offenses", "note": note("profile", "How each offense plays."), "rows": profile},
            {"id": "rails", "title": "Season rails", "note": note("rails", "The whole season, both teams."), "rows": rails},
        ]
        sheets[gid] = {
            "id": gid, "season": SEASON, "week": week, "when": when_et(ev["date"], tvalid), "tv": tv,
            "venue": venue.get("fullName") or "", "state": (venue.get("address") or {}).get("state") or "",
            "away": away, "home": home, "awayScore": scores["away"], "homeScore": scores["home"],
            "awayLeaders": leaders(A), "homeLeaders": leaders(H), "line": line, "sections": sections,
        }

        # ---- the desk: projected score and picks
        kick = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        prev = old_desk.get(gid)
        if prev and (state != "pre" or kick - now < timedelta(hours=2) or not prev.get("model")):
            desk.append(prev)  # lockable, played, or made by hand this week: keep it
            continue
        if ma and mh and ma.get("off_ppg") is not None and mh.get("off_ppg") is not None:
            ha_ = 0 if neutral else HFA / 2
            s_home = (mh["off_ppg"] + ma["def_ppg"]) / 2 + ha_
            s_away = (ma["off_ppg"] + mh["def_ppg"]) / 2 - ha_
            sm, st = s_home - s_away, s_home + s_away
        else:
            sm = st = None
        parts = [x for x in (sm, fm) if x is not None]
        model_m = sum(parts) / len(parts) if parts else None
        if model_m is None and mm is None:
            continue  # nothing to project (an FCS game with no line)
        dm = (mm + PULL * (model_m - mm)) if (mm is not None and model_m is not None) else (model_m if model_m is not None else mm)
        dt = (total + PULL * (st - total)) if (total is not None and st is not None) else (total if total is not None else st)
        if dt is None:
            continue
        home_pts, away_pts = round((dt + dm) / 2, 1), round((dt - dm) / 2, 1)
        pick, tpick, conf = "NO PLAY", "NO PLAY", 0
        if mm is not None and sm is not None and fm is not None:
            es, ef = sm - mm, fm - mm
            if abs(es) >= SIDE_GAP and abs(ef) >= SIDE_GAP and es * ef > 0:
                if es > 0:
                    pick = f"{ha} {spread:+.1f}"
                else:
                    pick = f"{aa} {-spread:+.1f}"
                conf = int(min(95, 50 + 4 * min(abs(es), abs(ef))))
        if total is not None and st is not None and abs(st - total) >= TOTAL_GAP:
            tpick = f"{'OVER' if st > total else 'UNDER'} {f1(total)}"
        desk.append({
            "id": gid, "name": ev.get("name") or "", "short": ev.get("shortName") or f"{aa} @ {ha}", "date": ev["date"],
            "away": away["name"], "home": home["name"], "awayAbbr": aa, "homeAbbr": ha,
            "awayPts": away_pts, "homePts": home_pts, "pick": pick, "total": tpick, "conf": conf or "",
            "spread": odds.get("details") or "", "totalLine": total, "model": MODEL,
        })

    slate.sort(key=lambda g: g["id"])
    order = {ev["id"]: ev["date"] for ev in board.get("events") or []}
    slate.sort(key=lambda g: order.get(g["id"], ""))
    return {"slate": {"season": SEASON, "week": week, "games": slate}, "sheets": sheets,
            "glossary": old.get("glossary") or [], "groups": old.get("groups") or [], "desk": desk}


# ---------------------------------------------------------------------------------------------
def read_page():
    s = PAGE.read_text(encoding="utf-8")
    i = s.find("const DATA =")
    j = s.find("{", i)
    obj, end = json.JSONDecoder().raw_decode(s, j)
    k = s.find(";", end)
    return s, i, k + 1, obj


def write_page(data):
    s, i, k, _ = read_page()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    PAGE.write_text(s[:i] + "const DATA = " + blob + ";" + s[k:], encoding="utf-8")


def fill_stuffs(data, adv):
    teams = (adv or {}).get("teams") or {}
    vals = sorted(((tid, t.get("stuffs_pg")) for tid, t in teams.items() if t.get("stuffs_pg") is not None), key=lambda x: -x[1])
    rank = {tid: i + 1 for i, (tid, _) in enumerate(vals)}
    for sh in data["sheets"].values():
        for sec in sh["sections"]:
            for row in sec["rows"]:
                if row["id"] != "stuffs" or sec["id"] != "rails":
                    continue
                for side, team in (("left", sh["away"]), ("right", sh["home"])):
                    t = teams.get(team["id"]) or {}
                    if t.get("stuffs_pg") is not None:
                        row[side] = cell(f"{t['stuffs_pg']:.1f}", rank.get(team["id"]), row[side]["caption"])


async def run_plays():
    """The Split's own play grading (refreshPlays), run once here instead of in every browser."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()

        async def route(r):
            url = r.request.url
            if url.startswith(SITE):
                path = url[len(SITE):].split("?")[0].split("#")[0].lstrip("/") or "index.html"
                f = ROOT / path
                if f.is_dir():
                    f = f / "index.html"
                if not f.exists():
                    return await r.fulfill(status=404, body=b"not found")
                return await r.fulfill(status=200, body=f.read_bytes(),
                                       headers={"content-type": mimetypes.guess_type(str(f))[0] or "application/octet-stream"})
            if r.request.resource_type in ("image", "font", "media", "stylesheet"):
                return await r.abort()
            try:
                resp = await r.fetch(timeout=45000)
                headers = dict(resp.headers)
                headers["access-control-allow-origin"] = "*"
                await r.fulfill(response=resp, headers=headers)
            except Exception:
                await r.abort()

        await ctx.route("**/*", route)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: print("page error:", str(e)[:200]))
        await page.goto(SITE + "/split/", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof PLAY_JOB !== 'undefined' && PLAY_JOB !== null", timeout=120000)
        adv = await page.evaluate("PLAY_JOB.then(() => (ADV && ADV.teams && Object.keys(ADV.teams).length >= 40) ? ADV : null)")
        stamp = await page.evaluate("PLAY_STAMP")
        await browser.close()
        return adv, stamp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int)
    ap.add_argument("--no-plays", action="store_true")
    args = ap.parse_args()
    week = args.week or current_week()
    _, _, _, old = read_page()
    if int((old.get("slate") or {}).get("week") or 0) != week:
        old = dict(old, desk=[])  # a new week: nothing from last week's desk carries over
    data = build(week, old)
    if len(data["slate"]["games"]) < 10:
        print("Fewer than 10 games came back; leaving The Split as it was.")
        return 0
    write_page(data)
    picks = sum(1 for r in data["desk"] if r.get("pick") not in (None, "", "NO PLAY"))
    totals = sum(1 for r in data["desk"] if r.get("total") not in (None, "", "NO PLAY"))
    print(f"  wrote week {week}: {len(data['slate']['games'])} games, {len(data['desk'])} desk rows, {picks} side picks, {totals} totals")
    if not args.no_plays:
        try:
            adv, stamp = asyncio.run(run_plays())
            if adv:
                ADV.write_text(json.dumps(adv, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
                print(f"  plays: {stamp}; {len(adv['teams'])} teams")
                fill_stuffs(data, adv)
                write_page(data)
            else:
                print("  plays: too few teams came back; kept the old plays file")
        except Exception as e:
            print("  plays failed:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
