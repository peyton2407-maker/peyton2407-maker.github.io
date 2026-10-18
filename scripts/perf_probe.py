#!/usr/bin/env python3
"""Where the live site keeps the browser busy, with real data from ESPN and the books.

Loads https://peyton2407-maker.github.io in headless Chromium (internet allowed, a phone-
sized screen, CPU slowed 4x like a mid-range phone), records every long task for 60 seconds
after each load, and samples the CPU to name the functions that take the time. Runs a fresh
load and then a reload, since visitors report the trouble on refresh.
Writes data/perf-probe.json.
Usage: python3 scripts/perf_probe.py
"""
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "perf-probe.json"
SITE = "https://peyton2407-maker.github.io"
INIT = """window.__lts = []; try { new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lts.push([Math.round(e.startTime), Math.round(e.duration)]))).observe({ type: 'longtask', buffered: true }); } catch (e) {}"""


def summarize(prof):
    nodes = {n["id"]: n for n in prof["nodes"]}
    parent = {}
    for n in prof["nodes"]:
        for c in n.get("children", []):
            parent[c] = n["id"]
    incl, selft = Counter(), Counter()
    for sid, d in zip(prof["samples"], prof["timeDeltas"]):
        cf = nodes[sid]["callFrame"]
        selft[(cf["functionName"] or "(anon)") + ":" + str(cf["lineNumber"])] += d
        seen, x = set(), sid
        while x is not None:
            cf = nodes[x]["callFrame"]
            k = (cf["functionName"] or "(anon)") + ":" + str(cf["lineNumber"])
            if k not in seen:
                incl[k] += d
                seen.add(k)
            x = parent.get(x)
    skip = ("(root)", "(idle)", "(program)", "(garbage collector)")
    top = lambda c: [[k, round(v / 1000)] for k, v in c.most_common(40) if not k.startswith(skip)][:25]
    return {"inclusive_ms": top(incl), "self_ms": top(selft), "idle_ms": round(incl.get("(idle):-1", 0) / 1000)}


async def one(browser, view, rate, reload, returning=False):
    ctx = await browser.new_context(viewport={"width": 390, "height": 844}, user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36")
    page = await ctx.new_page()
    await page.add_init_script(INIT)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    cdp = await ctx.new_cdp_session(page)
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
    if reload:
        await page.goto(SITE + "/#" + view, wait_until="load", timeout=120000)
        await page.wait_for_timeout(20000)
        if returning:  # browse like a visitor first, so the browser's saved data fills up
            for v in ("nfl", "props", "cfb", "cfbpicks", "builder", "score", "season", view):
                await page.evaluate(f"location.hash = '#{v}'")
                await page.wait_for_timeout(12000)
    await cdp.send("Profiler.enable")
    await cdp.send("Profiler.setSamplingInterval", {"interval": 2000})
    await cdp.send("Profiler.start")
    if reload:
        await page.reload(wait_until="load", timeout=120000)
    else:
        await page.goto(SITE + "/#" + view, wait_until="load", timeout=120000)
    await page.wait_for_timeout(60000)
    prof = (await cdp.send("Profiler.stop"))["profile"]
    lts = await page.evaluate("window.__lts")
    mem = await page.evaluate("""() => { let ls = 0; try { for (let i = 0; i < localStorage.length; i++) ls += (localStorage.getItem(localStorage.key(i)) || '').length; } catch (e) {}
        return { heap_mb: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null, dom_nodes: document.getElementsByTagName('*').length, saved_chars: ls }; }""")
    out = {
        "view": view, "cpu_slowdown": rate, "reload": reload, "returning": returning, "memory": mem,
        "long_tasks_total_ms": sum(d for _, d in lts),
        "longest_ms": max([d for _, d in lts], default=0),
        "over_1s": [x for x in lts if x[1] >= 1000][:20],
        "over_200ms": len([x for x in lts if x[1] >= 200]),
        "errors": errors[:10],
    }
    out.update(summarize(prof))
    await ctx.close()
    return out


async def main():
    report = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "runs": []}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for view, rate, reload, ret in (("home", 4, True, True), ("builder", 4, True, True), ("home", 4, False, False), ("nfl", 4, True, False)):
            try:
                r = await one(browser, view, rate, reload, ret)
            except Exception as e:
                r = {"view": view, "cpu_slowdown": rate, "reload": reload, "failed": str(e)[:300]}
            report["runs"].append(r)
            print(json.dumps({k: r.get(k) for k in ("view", "cpu_slowdown", "reload", "long_tasks_total_ms", "longest_ms", "over_200ms")}))
        await browser.close()
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
