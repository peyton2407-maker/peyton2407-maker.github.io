#!/usr/bin/env python3
"""Season odds: ESPN's season simulation next to the futures market.

ESPN's Football Power Index simulates the rest of each season; its feed carries, for every
team, the projected record and the chance to make the playoff, win the division or
conference, reach the title game and win it. This saves those for the NFL and college, and,
twice a week, the Super Bowl and college championship futures from The Odds API (1 credit
each; the same key as scripts/props.py). The market's chance is each price with the book's
cut taken out across the whole field.
Writes data/season.json. Rewritten only when something changed.
Usage: python3 scripts/season.py
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "season.json"
FPI = {
    "nfl": "https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/powerindex?limit=50",
    "cfb": "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?limit=150",
}
ODDS = "https://api.the-odds-api.com/v4"
BOOKS = "draftkings,fanduel,betmgm,williamhill_us,betrivers"
FUTURES_EVERY = timedelta(days=3.4)  # Mondays and Thursdays, about


def get_json(url, headers=False):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs season)"})
    with urllib.request.urlopen(req, timeout=40) as res:
        body = json.loads(res.read().decode("utf-8"))
        return (body, res.headers) if headers else body


def fpi_teams(league):
    d = get_json(FPI[league])
    names = {c["name"]: c["names"] for c in d.get("categories") or []}
    out = []
    for t in d.get("teams") or []:
        v = {}
        for c in t.get("categories") or []:
            for n, x in zip(names.get(c.get("name")) or [], c.get("values") or []):
                v.setdefault(c["name"] + "." + n, x)
        team = t["team"]
        logo = next((L["href"] for L in team.get("logos") or [] if "default" in (L.get("rel") or [])), "")
        g = lambda k: v.get(k)
        out.append({
            "id": str(team["id"]), "abbr": team.get("abbreviation"), "name": team.get("displayName"),
            "short": team.get("shortDisplayName") or team.get("nickname"), "logo": logo,
            "fpi": g("fpi.fpi"), "rank": g("fpi.fpirank"),
            "w": g("fpi.numwins"), "l": g("fpi.numlosses"), "t": g("fpi.numties"),
            "projW": g("fpi.projectedw"), "projL": g("fpi.projectedl"),
            "playoff": g("fpi.probmakeplayoffs"), "div": g("fpi.probwindiv"), "conf": g("fpi.probwinconf"),
            "titleGame": g("fpi.probmaketitlegame"), "title": g("fpi.probwintitle"), "winOut": g("fpi.probwinout"),
        })
    return out


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s or "").lower().replace("&", " and ")).strip()


def match_team(name, teams):
    """A futures name ("Georgia Bulldogs", "Miami (OH)", "Ohio State") to a team, strictly."""
    n = norm(name)
    for t in teams:
        if n in (norm(t["name"]), norm(t["short"])):
            return t
    for t in teams:  # "Georgia" -> "Georgia Bulldogs", but never "Georgia Tech Yellow Jackets"
        full = norm(t["name"])
        if full.startswith(n + " ") and not re.match(r"(state|st|tech|a and m|southern|international|atlantic)\b", full[len(n) + 1:]):
            return t
    return None


def futures(sport_hint, teams, key):
    sports, _ = get_json(f"{ODDS}/sports/?apiKey={urllib.parse.quote(key)}&all=false", headers=True)
    sk = next((s["key"] for s in sports if sport_hint in s["key"]), None)
    if not sk:
        return None, None
    data, hdr = get_json(f"{ODDS}/sports/{sk}/odds/?apiKey={urllib.parse.quote(key)}&regions=us&markets=outrights&oddsFormat=american&bookmakers={BOOKS}", headers=True)
    best, implied = {}, {}
    for ev in data or []:
        for bk in ev.get("bookmakers") or []:
            for mk in bk.get("markets") or []:
                outs = mk.get("outcomes") or []
                probs = {o["name"]: (100 / (o["price"] + 100) if o["price"] > 0 else -o["price"] / (-o["price"] + 100)) for o in outs if o.get("price")}
                total = sum(probs.values()) or 1
                for o in outs:
                    name, price = o.get("name"), o.get("price")
                    if not name or not price:
                        continue
                    if name not in best or price > best[name]["price"]:
                        best[name] = {"price": price, "book": bk.get("title") or bk.get("key")}
                    implied.setdefault(name, []).append(probs[name] / total)
    rows = {}
    for name, b in best.items():
        t = match_team(name, teams)
        if not t:
            continue
        ps = sorted(implied[name])
        rows[t["id"]] = {"price": b["price"], "book": b["book"], "market": round(ps[len(ps) // 2] * 100, 2)}
    return rows, hdr.get("x-requests-remaining")


def main():
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    now = datetime.now(timezone.utc)
    out = {"updated": old.get("updated"), "futuresAt": old.get("futuresAt"), "credits": old.get("credits"), "nfl": [], "cfb": []}
    for lg in ("nfl", "cfb"):
        try:
            out[lg] = fpi_teams(lg)
        except Exception as e:
            print(lg, "power index error:", e)
            out[lg] = old.get(lg) or []
    # futures: keep the last pull's numbers on each team until the next one
    for lg in ("nfl", "cfb"):
        prev = {t["id"]: t.get("futures") for t in old.get(lg) or [] if t.get("futures")}
        for t in out[lg]:
            if prev.get(t["id"]):
                t["futures"] = prev[t["id"]]
    due = not out["futuresAt"] or now - datetime.fromisoformat(out["futuresAt"].replace("Z", "+00:00")) > FUTURES_EVERY
    if due:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            import os
            from props import stored_key
            key = os.environ.get("ODDS_API_KEY", "").strip() or stored_key()
        except Exception:
            key = ""
        if key:
            pulled = False
            for lg, hint in (("nfl", "super_bowl_winner"), ("cfb", "ncaaf_championship_winner")):
                try:
                    rows, left = futures(hint, out[lg], key)
                    pulled = pulled or rows is not None
                    if rows:
                        for t in out[lg]:
                            t.pop("futures", None)
                            if t["id"] in rows:
                                t["futures"] = rows[t["id"]]
                        out["credits"] = left
                        print(f"{lg} futures: {len(rows)} teams priced; credits left {left}")
                except Exception as e:
                    print(lg, "futures error:", e)
            if pulled:  # a failed pull tries again next run instead of waiting days
                out["futuresAt"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if not out["nfl"] and not out["cfb"]:
        print("Nothing to save.")
        return 0
    same = json.dumps({k: out[k] for k in ("nfl", "cfb", "futuresAt")}, sort_keys=True) == json.dumps({k: old.get(k) for k in ("nfl", "cfb", "futuresAt")}, sort_keys=True)
    if same:
        print("No change.")
        return 0
    out["updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"season: {len(out['nfl'])} NFL and {len(out['cfb'])} college teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
