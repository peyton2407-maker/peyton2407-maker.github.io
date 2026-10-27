#!/usr/bin/env python3
"""Lock picks for everyone.

Opens the live Double Gs board in a headless browser (so it uses the same live ESPN
data and the same model code visitors get), then asks the page to:
  1. lock any pick, play of the day, or weekly card whose kickoff is 90 minutes away or less
  2. grade locked plays of the day that have finished
  3. move a finished week of locked picks into data/past-scorecards.json

Writes data/locks.json and data/past-scorecards.json only when something changed.

Usage:
    python3 scripts/lock_runner.py                    # normal run (GitHub Actions)
    python3 scripts/lock_runner.py --local . --now 2026-10-15T22:15:00Z
        # test run: serve this folder instead of the live site, internet blocked,
        # clock set to --now
"""
import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
LOCKS = ROOT / "data" / "locks.json"
PAST = ROOT / "data" / "past-scorecards.json"
REPORT = ROOT / "data" / "model-report.json"


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="serve this folder instead of the live site (testing)")
    ap.add_argument("--now", help="fake clock, ISO time (testing)")
    ap.add_argument("--settle", type=float, default=25, help="seconds to let live feeds load")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--inject", help="JS run before locking (testing only)")
    args = ap.parse_args()

    locks = read_json(LOCKS, {"v": 1, "plays": {}, "potd": {"nfl": [], "cfb": []}, "card": None})
    past = read_json(PAST, {})

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        # Always run this checkout's code and data (the live site can be a few minutes
        # behind its CDN cache). Live feeds like ESPN still load from the internet,
        # except in --local test runs where everything else is blocked.
        if True:
            root = Path(args.local or ROOT).resolve()
            offline = bool(args.local)

            async def route(r):
                url = r.request.url
                if not url.startswith(SITE):
                    return await (r.abort() if offline else r.continue_())
                path = url[len(SITE):].split("?")[0].split("#")[0].lstrip("/") or "index.html"
                f = root / path
                if f.is_dir():
                    f = f / "index.html"
                if not f.exists():
                    return await r.fulfill(status=404, body=b"not found")
                ct = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                return await r.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ct})

            await ctx.route("**/*", route)
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        if args.now:
            await page.clock.install(time=args.now)
        await page.goto(SITE + "/#score", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0", timeout=120000)
        if args.now:
            await page.clock.run_for(int(args.settle * 1000))
        else:
            await page.wait_for_timeout(int(args.settle * 1000))
        # The scorecards, results and published locks load after the board itself.
        await page.wait_for_function("!!window.PAST_CARDS && Array.isArray(window.WEEK_RESULTS)", timeout=60000)
        # Make sure scores and finals for this week and last week are in.
        await page.evaluate("async () => { try { if (typeof pullLiveScores === 'function') await pullLiveScores(false); } catch (e) {} }")
        # the box score numbers for player-prop plays of the day (scripts/prop_record.py)
        await page.evaluate("async () => { try { await pbFetchOnce('proprecord', '/data/prop-record.json?t=' + Date.now(), (d) => { window.PROP_RECORD = d; }); } catch (e) {} }")
        if args.inject:
            await page.evaluate(args.inject)
        result = await page.evaluate(
            """([locks, past]) => {
                const run = ggLockRun(locks);
                const arc = ggArchive(run.locks, past);
                const report = typeof ggModelReport === "function" ? ggModelReport(arc.past) : null;
                return { locks: arc.locks, past: arc.past, report, changes: run.changes.concat(arc.changes) };
            }""",
            [locks, past],
        )
        await browser.close()

    if errors:
        print("page errors:", *errors[:5], sep="\n  ")
    changes = result["changes"]
    if not changes:
        print("Nothing to lock, grade or archive.")
        return 0
    print("\n".join(changes))
    if args.dry_run:
        return 0
    new_locks = dump(result["locks"])
    if new_locks != dump(locks):
        LOCKS.write_text(new_locks, encoding="utf-8")
    rep = result.get("report")
    if rep and rep.get("games"):
        old = read_json(REPORT, {})
        strip = lambda d: {k: v for k, v in (d or {}).items() if k != "updated"}
        if strip(old) != strip(rep):
            REPORT.write_text(dump(rep), encoding="utf-8")
    if dump(result["past"]) != dump(past):
        # Keep the existing compact style of past-scorecards.json.
        PAST.write_text(json.dumps(result["past"], ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
