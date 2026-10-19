#!/usr/bin/env python3
"""Write the NFL board exactly as visitors' browsers show it into data/snapshot.json.

The snapshot's projections come from the board's first pass (projectGame); every visitor's
browser then settles them (blend with the opening line, follow line moves, quarterback news,
weather) before showing a pick. This opens this checkout's index.html in headless Chromium,
runs those same steps (settleBoard, applySituationalBoard) with the same inputs the page has
(depth charts, injury report, ESPN's ratings) and saves the settled numbers on each upcoming
NFL game. First paint, the record and every other reader of the snapshot then match what a
visitor sees. Settling again in the browser gives the same numbers (it starts from the
ratings and the shared opening line, not from these).
Usage: python3 scripts/settle_board.py
"""
import asyncio
import json
import mimetypes
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
SITE = "https://peyton2407-maker.github.io"
KEYS = ["blended_margin", "hashmark_home_spread", "hashmark_total", "home_points", "away_points", "edge_spread",
        "edge_total", "pick", "pick_line", "total_pick", "win_prob_home", "win_prob_away", "confidence",
        "model_total", "weather_adj_total", "market_margin", "settle_note"]
JS = """
async (keys) => {
  try { if (typeof pullNflDepth === "function") await pullNflDepth(); } catch (e) {}
  try { if (typeof installElevenReport === "function") await installElevenReport(); } catch (e) {}
  try { if (typeof fillNflOffenseDefense === "function") await fillNflOffenseDefense(); } catch (e) {}
  settleBoard();
  applySituationalBoard();
  const out = {};
  (DATA.games || []).forEach((g) => {
    if (!g || g.league !== "nfl" || g.completed || !g.proj) return;
    const p = {};
    keys.forEach((k) => { if (g.proj[k] !== undefined) p[k] = g.proj[k]; });
    out[String(g.id)] = p;
  });
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
        await page.wait_for_function("typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0 && typeof settleBoard === 'function'", timeout=120000)
        await page.wait_for_timeout(3000)
        out = await page.evaluate(JS, KEYS)
        await browser.close()
        return out


def main():
    try:
        settled = asyncio.run(run())
    except Exception as e:
        print("settle error:", str(e)[:300])
        return 0
    snap = json.loads(SNAP.read_text())
    n = 0
    for g in snap.get("games") or []:
        p = settled.get(str(g.get("id")))
        if not p or g.get("completed"):
            continue
        cur = g.setdefault("proj", {})
        before = json.dumps({k: cur.get(k) for k in KEYS}, sort_keys=True)
        for k in KEYS:
            if k in p:
                cur[k] = p[k]
        if json.dumps({k: cur.get(k) for k in KEYS}, sort_keys=True) != before:
            n += 1
    if n:
        SNAP.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    picks = sum(1 for p in settled.values() if p.get("pick") not in (None, "NO PLAY"))
    print(f"settled {len(settled)} upcoming NFL games ({picks} side picks); {n} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
