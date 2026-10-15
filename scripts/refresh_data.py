#!/usr/bin/env python3
"""Keep data/snapshot.json and data/week-results.json fresh from ESPN.

Downloads the NFL and college scoreboards (last week, this week, next week) and both
ESPN power indexes, then parses them with the board's own code (ggParseFeeds in
index.html, run in a headless browser) so the snapshot gets exactly what the site
expects. It then:
  - updates scores, status and lines on games already in the snapshot,
  - adds new games (with the board's projection) for this week and next,
  - replaces team ratings (college offense/defense on ESPN's 0-100 scale),
  - refreshes the ratings inside upcoming games' projections,
  - adds new finals to week-results.json.
Projections the board makes from these inputs are recomputed in the browser, so this
never edits picks. It refuses to write if the result looks wrong (fewer games, broken
scores, too few ratings).

Usage:
    python3 scripts/refresh_data.py                    # GitHub Actions
    python3 scripts/refresh_data.py --fixtures DIR --local . --now 2026-10-15T16:00:00Z
        # test run with saved ESPN JSON files instead of the internet
"""
import argparse
import asyncio
import json
import mimetypes
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
RESULTS = ROOT / "data" / "week-results.json"
STATUS = ROOT / "data" / "refresh-status.json"
REPORT = {"sources": []}  # what each feed returned; saved to data/refresh-status.json
SITE = "https://peyton2407-maker.github.io"
SB = {
    "nfl": "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?week={w}&seasontype=2&limit=50",
    "cfb": "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?week={w}&seasontype=2&groups=80&limit=300",
}
FPI = {
    "nfl": "https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/powerindex?limit=50",
    "cfb": "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?limit=200",
}
# ESPN serves different versions of the college index by URL; some leave out the
# offense/defense "efficiencies". Try these in order and keep the first that has them.
CFB_FPI_TRIES = [
    "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?limit=150",
    "https://site.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?limit=150",
    FPI["cfb"],
]


def efficiency_count(payload):
    n = 0
    for t in (payload or {}).get("teams") or []:
        for c in t.get("categories") or []:
            if c.get("name") == "efficiencies" and len(c.get("values") or []) >= 6:
                n += 1
    return n
# Fields that change on a game that is already in the snapshot.
LIVE_FIELDS = ["date", "status", "status_detail", "completed", "broadcasts"]
TEAM_FIELDS = ["score", "record", "rank", "winner"]
RATING_FIELDS = ["fpi", "fpi_rank", "off", "def"]


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs data refresh)"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode("utf-8"))


def week_numbers(now):
    """Same week clock as the site (weeks start Tuesdays)."""
    def week_from(start):
        days = (now - start).days
        return max(1, days // 7 + 1)
    nfl = week_from(datetime(2026, 9, 8, 16, tzinfo=timezone.utc))
    cfb = week_from(datetime(2026, 9, 1, 16, tzinfo=timezone.utc))
    return nfl, cfb


def load_feeds(args, nfl_w, cfb_w):
    boards, fpi = [], {}
    for lg, cur in (("nfl", nfl_w), ("cfb", cfb_w)):
        for w in (cur - 1, cur, cur + 1):
            if w < 1:
                continue
            if args.fixtures:
                f = Path(args.fixtures) / f"{lg}-{w}.json"
                if not f.exists():
                    continue
                payload = json.loads(f.read_text())
            else:
                try:
                    payload = get_json(SB[lg].format(w=w))
                except Exception as e:  # one week missing is not fatal
                    print(f"skip {lg} week {w}: {e}")
                    REPORT["sources"].append({"feed": f"{lg} scoreboard week {w}", "error": str(e)[:200]})
                    continue
                REPORT["sources"].append({"feed": f"{lg} scoreboard week {w}", "events": len(payload.get("events") or [])})
            boards.append({"league": lg, "week": w, "payload": payload})
        if args.fixtures:
            f = Path(args.fixtures) / f"fpi-{lg}.json"
            fpi[lg] = json.loads(f.read_text()) if f.exists() else None
        elif lg == "cfb":
            best, best_n = None, -1
            for url in CFB_FPI_TRIES:
                try:
                    payload = get_json(url)
                except Exception as e:
                    print(f"college index failed at {url}: {e}")
                    REPORT["sources"].append({"feed": url, "error": str(e)[:200]})
                    continue
                n = efficiency_count(payload)
                REPORT["sources"].append({"feed": url, "teams": len(payload.get("teams") or []), "with_offense_defense": n})
                print(f"college index {url.split('?')[0].split('//')[1].split('/')[0]} ?{url.split('?')[1]}: {len(payload.get('teams') or [])} teams, {n} with offense/defense")
                if n > best_n:
                    best, best_n = payload, n
                if n >= 100:
                    break
            fpi[lg] = best
        else:
            try:
                fpi[lg] = get_json(FPI[lg])
                REPORT["sources"].append({"feed": FPI[lg], "teams": len(fpi[lg].get("teams") or [])})
            except Exception as e:
                fpi[lg] = None
                REPORT["sources"].append({"feed": FPI[lg], "error": str(e)[:200]})
    return {"boards": boards, "fpi": fpi}


async def parse_in_page(args, feeds):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        # Always run this checkout's code, not whatever the live site has cached.
        if True:
            root = Path(args.local or ROOT).resolve()

            async def route(r):
                url = r.request.url
                if not url.startswith(SITE):
                    return await r.abort()
                path = url[len(SITE):].split("?")[0].split("#")[0].lstrip("/") or "index.html"
                f = root / path
                if f.is_dir():
                    f = f / "index.html"
                if not f.exists():
                    return await r.fulfill(status=404, body=b"not found")
                return await r.fulfill(status=200, body=f.read_bytes(),
                                       headers={"content-type": mimetypes.guess_type(str(f))[0] or "application/octet-stream"})
            await ctx.route("**/*", route)
        page = await ctx.new_page()
        if args.now:
            await page.clock.install(time=args.now)
        await page.goto(SITE + "/#home", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof ggParseFeeds === 'function' && typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0", timeout=120000)
        out = await page.evaluate("(feeds) => ggParseFeeds(feeds)", feeds)
        await browser.close()
        return out


def merge(snap, results, parsed, nfl_w, cfb_w, now_iso):
    changes = []
    games = snap.get("games", [])
    by_id = {str(g["id"]): g for g in games}
    ratings = parsed["ratings"]
    rmap = {lg: {str(r["id"]): r for r in ratings.get(lg) or []} for lg in ("nfl", "cfb")}

    # College offense/defense: if the feed's unit ratings didn't come through for most
    # teams, keep the ones already saved (never wipe them).
    old_cfb = {str(r["id"]): r for r in (snap.get("ratings", {}).get("cfb") or [])}
    cfb_new = ratings.get("cfb") or []
    if sum(1 for r in cfb_new if r.get("off") is not None) < 100:
        print("college unit ratings missing from the feed; keeping saved ones")
        REPORT.setdefault("notes", []).append("college offense/defense missing from the feed; kept saved ones")
        for r in cfb_new:
            o = old_cfb.get(str(r["id"]))
            if o and r.get("off") is None:
                r["off"], r["def"] = o.get("off"), o.get("def")
        rmap["cfb"] = {str(r["id"]): r for r in cfb_new}
    # Ratings: only replace a league when the feed came back with a full table.
    for lg, need in (("nfl", 30), ("cfb", 100)):
        lst = ratings.get(lg) or []
        if len(lst) >= need:
            snap.setdefault("ratings", {})[lg] = lst
        else:
            rmap[lg] = {str(r["id"]): r for r in (snap.get("ratings", {}).get(lg) or [])}
            print(f"kept old {lg} ratings (feed had {len(lst)})")
            REPORT.setdefault("notes", []).append(f"kept saved {lg} ratings (feed had {len(lst)} teams)")

    added = updated = finals = 0
    for item in parsed["games"]:
        g, proj = item["game"], item["proj"]
        gid = str(g["id"])
        old = by_id.get(gid)
        if old is None:
            new = dict(g)
            for k in ("period", "clock", "situation", "officials", "referee"):
                new.pop(k, None)
            new["proj"] = {k: v for k, v in (proj or {}).items() if v is not None}
            if new["league"] == "cfb":
                new.setdefault("props", [])
            games.append(new)
            by_id[gid] = new
            added += 1
            continue
        before = json.dumps(old, sort_keys=True)
        for k in LIVE_FIELDS:
            if g.get(k) not in (None, "", []):
                old[k] = g[k]
        for side in ("home", "away"):
            for k in TEAM_FIELDS:
                if k in g.get(side, {}):
                    old.setdefault(side, {})[k] = g[side][k]
        o = g.get("odds") or {}
        if o.get("home_spread") is not None or o.get("total") is not None:
            old["odds"] = {**(old.get("odds") or {}), **{k: v for k, v in o.items() if v is not None}}
        # Refresh team ratings inside upcoming games (the browser rebuilds the numbers).
        if not old.get("completed"):
            p = old.setdefault("proj", {})
            for side in ("home", "away"):
                r = rmap[old["league"]].get(str(old[side]["id"]))
                if not r:
                    continue
                for k in RATING_FIELDS:
                    key = f"{side}_{k}"
                    if r.get(k) is not None:
                        p[key] = r[k]
                    elif k in ("off", "def"):
                        p.pop(key, None)  # no unit rating beats a wrong-scale one
        if json.dumps(old, sort_keys=True) != before:
            updated += 1

    have = {str(r["id"]) for r in results}
    for g in games:
        if not g.get("completed") or str(g["id"]) in have:
            continue
        try:
            hs, as_ = int(float(g["home"]["score"])), int(float(g["away"]["score"]))
        except (TypeError, ValueError, KeyError):
            continue
        if not str(g.get("status", "")).upper().startswith("STATUS_FINAL"):
            continue
        results.append({"id": str(g["id"]), "league": g["league"], "date": g["date"],
                        "name": g.get("short_name"), "homeId": g["home"]["id"], "awayId": g["away"]["id"],
                        "homeAbbr": g["home"]["abbr"], "awayAbbr": g["away"]["abbr"],
                        "hs": hs, "as": as_, "spread": None, "total": None})
        have.add(str(g["id"]))
        finals += 1

    if added or updated or finals:
        snap["generated_at"] = now_iso
        snap.setdefault("meta", {}).update({"nfl_week": nfl_w, "cfb_weeks": [cfb_w], "nfl_next_week": nfl_w + 1})
        changes.append(f"{added} new games, {updated} updated, {finals} new finals")
    return changes


def validate(old_snap, snap, results):
    games = snap.get("games", [])
    ids = [str(g["id"]) for g in games]
    assert len(ids) == len(set(ids)), "duplicate game ids"
    assert len(games) >= len(old_snap.get("games", [])), "games went missing"
    for g in games:
        assert g.get("league") in ("nfl", "cfb") and g.get("home") and g.get("away"), f"bad game {g.get('id')}"
        if g.get("completed") and str(g.get("status", "")).upper().startswith("STATUS_FINAL"):
            float(g["home"]["score"]), float(g["away"]["score"])
    assert len(snap["ratings"]["nfl"]) >= 30 and len(snap["ratings"]["cfb"]) >= 100, "too few ratings"
    assert len(results) == len({str(r["id"]) for r in results}), "duplicate results"
    json.loads(json.dumps(snap))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures")
    ap.add_argument("--local")
    ap.add_argument("--now")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    nfl_w, cfb_w = week_numbers(now)
    feeds = load_feeds(args, nfl_w, cfb_w)
    parsed = asyncio.run(parse_in_page(args, feeds))
    raw = SNAP.read_text(encoding="utf-8")
    snap, old_snap = json.loads(raw), json.loads(raw)
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    changes = merge(snap, results, parsed, nfl_w, cfb_w, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    REPORT.update({"ran_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "nfl_week": nfl_w, "cfb_week": cfb_w, "changes": changes})
    if not args.dry_run:
        STATUS.write_text(json.dumps(REPORT, indent=1) + "\n", encoding="utf-8")
    if not changes:
        print("No changes.")
        return 0
    validate(old_snap, snap, results)
    print("\n".join(changes))
    if args.dry_run:
        return 0
    SNAP.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
