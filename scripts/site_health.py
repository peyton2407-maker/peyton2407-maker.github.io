#!/usr/bin/env python3
"""Live health check of the site in a real browser.

Opens the live Double Gs site like a visitor (real Chrome, real internet, real
cross-site rules), lets the live feeds load, then visits the screens that depend on
live data and writes what it saw to data/site-health.json:
  - JavaScript errors and console errors
  - every failed or blocked request to a data source (ESPN, DraftKings, weather, ...)
  - per screen: how much loaded (cards, players, tickets) and the summary line

Usage:
    python3 scripts/site_health.py               # GitHub Actions
    python3 scripts/site_health.py --print       # also print the report
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "site-health.json"
SITE = "https://peyton2407-maker.github.io"

# view -> (selector to count, how to set it up before reading)
SCREENS = {  # view -> (section id, what to count, setup before reading)
    "home": ("homeSection", "#homeBoard .game-row", None),
    "nfl": ("boardSection", ".slate-row, article.game", None),
    "cfb": ("boardSection", ".slate-row, article.game", None),
    "builder": ("builderSection", ".pb-game", None),
    "season": ("seasonSection", "tr[data-team]", None),
    "score": ("scoreSection", "tr, .score-row", None),
    "ratings": ("ratingsSection", "tr[data-id], .rank-card", None),
    "card": ("cardSection", ".share-legs li", None),
    "props": ("propsSection", ".prop-card", "document.getElementById('propDay') && (document.getElementById('propDay').value='week', document.getElementById('propDay').dispatchEvent(new Event('change')))"),
    "tds": ("tdSection", "#tdBoard > *", None),
    "charts": ("chartsSection", "#chartGames [data-chart-game]", None),
    "value": ("valueSection", ".prop-card, .value-tile", None),
    "parlay": ("parlaySection", ".parlay-card", None),
    "live": ("boardSection", ".card", None),
    "nflinj": ("injSection", "#injBoard > *", None),
    "nflwx": ("nflWxSection", "#nflWxBoard > *", None),
    "nflpotd": ("nflPotdSection", "#nflPotdBoard > *", None),
    "cfbpicks": ("cfbPicksSection", ".prop-card, article", None),
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--settle", type=int, default=45)
    args = ap.parse_args()
    report = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "errors": [], "console": [],
              "failed_requests": {}, "bad_status": {}, "screens": {}}

    def host(url):
        return urlparse(url).netloc or url[:40]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        page.on("pageerror", lambda e: report["errors"].append(str(e)[:300]))
        page.on("console", lambda m: m.type == "error" and len(report["console"]) < 60 and report["console"].append(m.text[:240]))

        def failed(r):
            h = host(r.url)
            if h.endswith("github.io"):
                return
            e = report["failed_requests"].setdefault(h, {"count": 0, "example": r.url[:200], "reason": r.failure})
            e["count"] += 1

        def response(r):
            if r.status >= 400:
                h = host(r.url)
                e = report["bad_status"].setdefault(h, {"count": 0, "statuses": {}, "example": r.url[:200]})
                e["count"] += 1
                e["statuses"][str(r.status)] = e["statuses"].get(str(r.status), 0) + 1

        page.on("requestfailed", failed)
        page.on("response", response)
        await page.goto(SITE + "/#home", wait_until="load", timeout=120000)
        await page.wait_for_timeout(args.settle * 1000)
        for view, (sec_id, sel, setup) in SCREENS.items():
            await page.evaluate(f"location.hash = '#{view}'")
            await page.wait_for_timeout(4000)
            if setup:
                await page.evaluate(setup)
                await page.wait_for_timeout(4000)
            info = await page.evaluate(
                """([secId, sel]) => {
                    const sec = document.getElementById(secId) || document.body;
                    const text = sec.innerText.replace(/\\s+/g, ' ');
                    const summary = (text.match(/\\b\\d+ (featured|matching|TD tickets|value tickets|games on this board|listed|spread tickets|first-TD)[^.]{0,60}/g) || []).slice(0, 4);
                    const empty = [...sec.querySelectorAll('.empty')].filter((e) => e.offsetParent).map((e) => e.textContent.trim().slice(0, 140));
                    // pictures: anything that finished loading with nothing to show is broken
                    const imgs = [...sec.querySelectorAll('img')].filter((i) => i.offsetParent && i.complete && getComputedStyle(i).visibility !== 'hidden');
                    const broken = imgs.filter((i) => i.naturalWidth === 0).map((i) => i.src.slice(-60)).slice(0, 5);
                    return { visible: !!sec.offsetParent, count: sec.querySelectorAll(sel).length, summary, empty, chars: text.length, images: imgs.length, broken_images: broken };
                }""",
                [sec_id, sel],
            )
            report["screens"][view] = info
        # a game opens in the pop-up, once
        await page.evaluate("location.hash = '#nfl'")
        await page.wait_for_timeout(3000)
        report["game_popup"] = await page.evaluate("""() => { const r = document.querySelector('.slate-row[data-id], article.game[data-id]'); if (!r) return 'no game row';
            r.click(); return new Promise((res) => setTimeout(() => { const ov = document.getElementById('overlay'); const sheet = document.getElementById('gameSheet');
              res({ open: !!(ov && ov.classList.contains('show')), hero: !!document.querySelector('#modal .gm-hero'), shown_twice: !!(sheet && sheet.offsetParent && sheet.innerHTML.length > 50),
                    logos_ok: [...document.querySelectorAll('#modal img')].filter((i) => i.complete && i.naturalWidth > 0).length }); }, 2500)); }""")
        # The Split
        sp = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        sp_err = []
        sp.on("pageerror", lambda e: sp_err.append(str(e)[:200]))
        await sp.goto(SITE + "/split/", wait_until="load", timeout=120000)
        await sp.wait_for_timeout(5000)
        report["split"] = await sp.evaluate("""() => { const imgs = [...document.querySelectorAll('img')].filter((i) => i.complete && i.offsetParent);
            return { games: document.querySelectorAll('[data-gid], .game, article').length, images: imgs.length, broken_images: imgs.filter((i) => i.naturalWidth === 0).map((i) => i.src.slice(-60)).slice(0, 5) }; }""")
        report["split"]["errors"] = sp_err
        report["dk_lines_loaded"] = await page.evaluate("Object.keys(window.__DK_LINES || window.DK_LINES || {}).length || null")
        report["games_with_props"] = await page.evaluate("(DATA.games || []).filter((g) => g.league === 'nfl' && !g.completed && (g.props || []).length).length")
        report["nfl_games_upcoming"] = await page.evaluate("(DATA.games || []).filter((g) => g.league === 'nfl' && !g.completed).length")
        await browser.close()

    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if args.print:
        print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
