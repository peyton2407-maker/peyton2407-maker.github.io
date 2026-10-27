#!/usr/bin/env python3
"""The prop record: every player-prop side the site posts, saved before kickoff and graded.

Every hour this opens this checkout's index.html in headless Chromium (internet allowed, the
same way scripts/gamelogs.py does) and asks the page for its posted side on every player with
sportsbook lines (propRecordPicks: the side, line, best price and book, our chance, the
books' chance and the value at that price). Until kickoff each entry is replaced by the
newest one (projections and injuries change); a player who drops off before kickoff (ruled
out, lines pulled) is removed. At kickoff the entry is frozen.

After the game is final the entry is graded from ESPN's box score (game logs in
data/gamelogs.json as a fallback): win, loss or push at the saved line, and units for one
unit at the saved price. A player missing from the box score is a void, as at the books.
Writes data/prop-record.json: {"updated", "picks": [...]}. Never fails the job.

Usage:
    python3 scripts/prop_record.py
    python3 scripts/prop_record.py --fixture DIR [--now ISO]   # test: DIR/picks.json, DIR/summary-<game id>.json
"""
import argparse
import asyncio
import json
import mimetypes
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
OUT = ROOT / "data" / "prop-record.json"
LOGS = ROOT / "data" / "gamelogs.json"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={id}"
# stat -> (box score category, key, the label ESPN shows when keys are missing)
BOX = {
    "pass_yds": ("passing", "passingYards", "YDS"),
    "pass_td": ("passing", "passingTouchdowns", "TD"),
    "rush_yds": ("rushing", "rushingYards", "YDS"),
    "rec_yds": ("receiving", "receivingYards", "YDS"),
    "rec": ("receiving", "receptions", "REC"),
}
VOID_AFTER = timedelta(days=4)   # no box score and no game log by then: void


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    try:
        s = str(s).replace("Z", "+00:00")
        if len(s) == 16 + 6:  # "2026-10-18T20:05+00:00"
            s = s[:16] + ":00" + s[16:]
        return datetime.fromisoformat(s)
    except Exception:
        return None


async def page_picks():
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
            if r.request.resource_type in ("image", "font", "media", "stylesheet") or (urlparse(url).hostname or "") in ("corsproxy.io", "api.allorigins.win"):
                return await r.abort()
            try:
                resp = await r.fetch(timeout=30000)
                headers = dict(resp.headers)
                headers["access-control-allow-origin"] = "*"
                await r.fulfill(response=resp, headers=headers)
            except Exception:
                await r.abort()

        await ctx.route("**/*", route)
        page = await ctx.new_page()
        await page.goto(SITE + "/#home", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0", timeout=120000)
        await page.wait_for_timeout(5000)
        res = await page.evaluate("async () => await propRecordPicks()")
        await browser.close()
        return res


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs prop record)"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode("utf-8"))


def box_stats(summary):
    """{"final": bool, "players": {athlete id: {stat: value}}} from an ESPN game summary."""
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    st = (comp.get("status") or {}).get("type") or {}
    final = bool(st.get("completed")) or st.get("state") == "post"
    players = {}
    for team in ((summary.get("boxscore") or {}).get("players") or []):
        for cat in team.get("statistics") or []:
            name = cat.get("name")
            keys = cat.get("keys") or []
            labels = cat.get("labels") or []
            for a in cat.get("athletes") or []:
                pid = str((a.get("athlete") or {}).get("id") or "")
                if not pid:
                    continue
                row = players.setdefault(pid, {})
                stats = a.get("stats") or []
                for stat, (c, key, label) in BOX.items():
                    if c != name:
                        continue
                    i = keys.index(key) if key in keys else (labels.index(label) if label in labels else -1)
                    if 0 <= i < len(stats):
                        try:
                            row[stat] = float(str(stats[i]).replace(",", ""))
                        except ValueError:
                            pass
    return {"final": final, "players": players}


def grade(pick, actual):
    line, take, price = float(pick["line"]), pick["take"], float(pick["price"])
    if abs(actual - line) < 1e-9:
        out = "push"
    elif (actual > line) == (take == "over"):
        out = "win"
    else:
        out = "loss"
    dec = 1 + (price / 100 if price > 0 else 100 / -price)
    units = round(dec - 1, 3) if out == "win" else (-1.0 if out == "loss" else 0.0)
    a = int(actual) if float(actual).is_integer() else actual
    return {"actual": a, "out": out, "units": units}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--now")
    args = ap.parse_args()
    now = parse(args.now) if args.now else datetime.now(timezone.utc)
    fx = Path(args.fixture) if args.fixture else None
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    book = {f"{x['gid']}|{x['pid']}": x for x in old.get("picks") or []}
    changed = False

    # 1) log the page's current sides for games that haven't kicked off
    try:
        res = json.loads((fx / "picks.json").read_text()) if fx else asyncio.run(page_picks())
    except Exception as e:
        print("page error:", str(e)[:300])
        res = None
    if res:
        lined = set(res.get("lined") or [])
        seen = set()
        for pk in res.get("picks") or []:
            kick = parse(pk.get("kick"))
            if not kick or kick <= now:
                continue
            k = f"{pk['gid']}|{pk['pid']}"
            seen.add(k)
            prev = book.get(k)
            pk = dict(pk, at=iso(now), first=(prev or {}).get("first") or iso(now))
            if prev and prev.get("result"):
                continue
            if {kk: v for kk, v in (prev or {}).items() if kk != "at"} != {kk: v for kk, v in pk.items() if kk != "at"}:
                changed = True
            book[k] = pk
        # a player dropped before kickoff (out, lines pulled) leaves the record; only for games
        # the page had lines for this run, so a failed load never empties the record
        for k, x in list(book.items()):
            kick = parse(x.get("kick"))
            if k not in seen and x["gid"] in lined and kick and kick > now and not x.get("result"):
                del book[k]
                changed = True
        print(f"{len(res.get('picks') or [])} sides on the page; {len(lined)} games with lines")

    # 2) grade frozen picks whose game is over
    try:
        logs = (json.loads(LOGS.read_text()).get("players") or {}) if LOGS.exists() else {}
    except Exception:
        logs = {}
    todo = [x for x in book.values() if not x.get("result") and parse(x.get("kick")) and parse(x["kick"]) < now - timedelta(hours=3)]
    boxes = {}
    for x in todo:
        gid = x["gid"]
        if gid not in boxes:
            try:
                s = json.loads((fx / f"summary-{gid}.json").read_text()) if fx else get_json(SUMMARY.format(id=gid))
                boxes[gid] = box_stats(s)
            except Exception as e:
                print("box score error", gid, str(e)[:120])
                boxes[gid] = None
        b = boxes[gid]
        actual = None
        if b and b["final"]:
            row = b["players"].get(str(x["pid"]))
            if row is not None:
                actual = row.get(x["stat"], 0.0)   # in the box score without this stat: 0
        if actual is None:  # game log fallback: the row on the game's date against this opponent
            kick = parse(x["kick"])
            for r in (logs.get(str(x["pid"])) or {}).get("rows") or []:
                d = parse(r.get("d") + "T12:00:00Z") if r.get("d") else None
                if d and abs((d - kick).total_seconds()) < 36 * 3600 and r.get("o") == x.get("opp") and r.get(x["stat"]) is not None:
                    actual = float(r[x["stat"]])
                    break
        if actual is not None:
            x["result"] = grade(x, actual)
            changed = True
        elif b and b["final"] and str(x["pid"]) not in b["players"]:
            x["result"] = {"actual": None, "out": "void", "units": 0.0, "why": "not in the box score"}
            changed = True
        elif now - parse(x["kick"]) > VOID_AFTER:
            x["result"] = {"actual": None, "out": "void", "units": 0.0, "why": "no stats found"}
            changed = True

    # 3) the box score number for NFL plays of the day that are player props (data/locks.json
    # potd rows with "prop"); the page grades them against their own line
    potd = dict(old.get("potd") or {})
    try:
        locks = json.loads((ROOT / "data" / "locks.json").read_text())
    except Exception:
        locks = {}
    for r in ((locks.get("potd") or {}).get("nfl") or []):
        pr = r.get("prop")
        kick = parse(r.get("kick"))
        if not pr or not r.get("key") or r.get("result") or r["key"] in potd or not kick or kick > now - timedelta(hours=3):
            continue
        gid = str(r.get("id"))
        if gid not in boxes:
            try:
                s = json.loads((fx / f"summary-{gid}.json").read_text()) if fx else get_json(SUMMARY.format(id=gid))
                boxes[gid] = box_stats(s)
            except Exception as e:
                print("box score error", gid, str(e)[:120])
                boxes[gid] = None
        b = boxes[gid]
        if not b or not b["final"]:
            continue
        row = b["players"].get(str(pr.get("pid")))
        if row is None:
            potd[r["key"]] = {"pid": pr.get("pid"), "stat": pr.get("stat"), "actual": None, "void": True}
        else:
            v = row.get(pr.get("stat"), 0.0)
            potd[r["key"]] = {"pid": pr.get("pid"), "stat": pr.get("stat"), "actual": int(v) if float(v).is_integer() else v}
        changed = True
        print("play of the day prop", r.get("line"), "->", potd[r["key"]])

    graded = [x for x in book.values() if x.get("result") and x["result"]["out"] != "void"]
    print(f"{len(book)} picks in the record; {len(graded)} graded; {len(todo)} were waiting on a result")
    if not changed and OUT.exists():
        print("No change.")
        return 0
    picks = sorted(book.values(), key=lambda x: (str(x.get("kick")), x.get("name") or ""))
    OUT.write_text(json.dumps({"updated": iso(now), "picks": picks, "potd": potd}, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never fail the job
        print("prop record error:", e)
        sys.exit(0)
