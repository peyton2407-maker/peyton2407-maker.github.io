#!/usr/bin/env python3
"""Live weather and injury reports for every visitor, run on the server.

The site's weather (Open-Meteo at each stadium) and injury reports (ESPN, plus Covers for
college) used to be pulled only inside a visitor's browser, so they went stale whenever
nobody had the page open, and college injuries depended on free CORS relays that often
fail. This opens this checkout's own index.html in headless Chromium with internet access,
runs the site's own code (attachWeather, fetchInjuries) so the numbers match the page
exactly, and saves:
  data/eleven.json    the latest report the page loads on start (installElevenReport):
                      NFL and college injuries, and weather for every upcoming game
  data/snapshot.json  each upcoming game's forecast, so the board's weather adjustments
                      use it for everyone on first paint
Requests leave from the server, so Covers is read directly (no relay).
Usage: python3 scripts/gameday.py
"""
import asyncio
import json
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "eleven.json"
BLOCK = {"corsproxy.io", "api.allorigins.win", "www.googletagmanager.com", "fonts.googleapis.com", "fonts.gstatic.com"}

JS = """
async () => {
  const now = Date.now();
  const out = { wx: {}, wxNfl: [], wxCfb: [], nfl: [], cfb: [], notes: [] };
  const games = (DATA.games || []).filter((g) => (g.league === "nfl" || g.league === "cfb") && !g.completed && g.date
    && Date.parse(g.date) > now - 4 * 3600e3 && Date.parse(g.date) < now + 8 * 86400e3);
  try {
    await attachWeather(games);
  } catch (e) { out.notes.push("weather: " + e); }
  games.forEach((g) => {
    const w = g.weather;
    if (w && (w.indoor || w.temp_f != null)) out.wx[String(g.id)] = { weather: w, weather_impact: g.weather_impact || null };
  });
  out.wxNfl = games.filter((g) => g.league === "nfl" && g.weather).map(slimWx);
  out.wxCfb = games.filter((g) => g.league === "cfb" && g.weather).map(slimWx);
  out.games = games.length;
  const clean = (rows) => JSON.parse(JSON.stringify((rows || []).map((r) => {
    const o = {}; Object.keys(r).forEach((k) => { if (!k.startsWith("_")) o[k] = r[k]; }); return o;
  })));
  try { view = "cfbinj"; await fetchInjuries(true); const p = ensureInjPack(); out.cfb = clean(p.cfb); out.cfbSource = p.cfbLive || ""; }
  catch (e) { out.notes.push("cfb injuries: " + e); }
  try { view = "nflinj"; await fetchInjuries(true); const p = ensureInjPack(); out.nfl = clean(p.nfl); }
  catch (e) { out.notes.push("nfl injuries: " + e); }
  out.et = etFields();
  return out;
}
"""


async def run():
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
            host = urlparse(url).hostname or ""
            if host in BLOCK or r.request.resource_type in ("image", "font", "media", "stylesheet"):
                return await r.abort()
            # Fetch from the server and hand it back with CORS opened, so the page can read
            # sources a browser would block (Covers) without a public relay.
            try:
                resp = await r.fetch(timeout=30000)
                headers = dict(resp.headers)
                headers["access-control-allow-origin"] = "*"
                await r.fulfill(response=resp, headers=headers)
            except Exception:
                await r.abort()

        await ctx.route("**/*", route)
        page = await ctx.new_page()
        page.on("pageerror", lambda e: print("page error:", str(e)[:200]))
        await page.goto(SITE + "/#home", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0", timeout=120000)
        await page.wait_for_timeout(4000)
        out = await page.evaluate(JS)
        await browser.close()
        return out


def main():
    out = asyncio.run(run())
    et = out.get("et") or {}
    now = datetime.now(timezone.utc)
    print(f"{out.get('games')} upcoming games, weather for {len(out['wx'])}; "
          f"injuries: {len(out['nfl'])} NFL, {len(out['cfb'])} college ({out.get('cfbSource') or 'no source'})")
    for n in out.get("notes") or []:
        print("note:", n)

    # 1) the latest report the page installs on load
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    fresh_old = old.get("ymd") == et.get("ymd")
    hour = int(et.get("hour") or 0)
    label = f"Updated {hour % 12 or 12}:{int(et.get('minute') or 0):02d} {'PM' if hour >= 12 else 'AM'} ET"
    report = {
        "ymd": et.get("ymd") or now.strftime("%Y-%m-%d"),
        "weekday": et.get("weekday") or now.strftime("%a"),
        "label": label,
        "saved": int(now.timestamp() * 1000),
        # an empty pull keeps today's earlier list rather than wiping it
        "nfl": out["nfl"] or (old.get("nfl") if fresh_old else []) or [],
        "cfb": out["cfb"] or (old.get("cfb") if fresh_old else []) or [],
        "wxNfl": out["wxNfl"] or (old.get("wxNfl") if fresh_old else []) or [],
        "wxCfb": out["wxCfb"] or (old.get("wxCfb") if fresh_old else []) or [],
    }
    if not (report["nfl"] or report["cfb"] or report["wxNfl"] or report["wxCfb"]):
        print("Nothing came back; leaving data/eleven.json as it was.")
        return 0
    OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")

    # 2) each upcoming game's forecast in the snapshot
    if out["wx"]:
        snap = json.loads(SNAP.read_text())
        n = 0
        for g in snap.get("games") or []:
            w = out["wx"].get(str(g.get("id")))
            if not w or g.get("completed"):
                continue
            if g.get("weather") != w["weather"]:
                g["weather"] = w["weather"]
                if w.get("weather_impact"):
                    g["weather_impact"] = w["weather_impact"]
                n += 1
        if n:
            SNAP.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"snapshot: updated the forecast for {n} games")
    return 0


if __name__ == "__main__":
    sys.exit(main())
