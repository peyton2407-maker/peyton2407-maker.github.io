#!/usr/bin/env python3
"""Recent game logs for every NFL player on the board, for the props page's hit rates.

Opens this checkout's index.html in headless Chromium (internet allowed), finds every player
with a projection in an NFL game from now to nine days out, and reads each one's ESPN game
log for this season and last (the page's own parseGamelog), keeping the 17 most recent
games. A player fetched in the last 20 hours is skipped, so the job is cheap to run often.
Writes data/gamelogs.json: {"updated", "players": {id: {"at", "pos", "rows": [...]}}}; each row has
date, opp and the stats (pass_yds, pass_td, pass_att, cmp, rush_yds, rush_att, rec, rec_yds,
td). Players no longer on the board drop off after two weeks.
Usage: python3 scripts/gamelogs.py
"""
import asyncio
import json
import mimetypes
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
OUT = ROOT / "data" / "gamelogs.json"
KEEP = ["pass_yds", "pass_td", "pass_att", "cmp", "rush_yds", "rush_att", "rec", "rec_yds", "td"]

JS = """
async (skip) => {
  try { if (typeof ensureWeekProps === "function") await ensureWeekProps(); } catch (e) {}
  const now = Date.now();
  const ids = new Set();
  const pos = {};
  (DATA.games || []).forEach((g) => {
    if (g.league !== "nfl" || g.completed || !g.date) return;
    const t = Date.parse(g.date);
    if (!(t > now - 4 * 3600e3 && t < now + 9 * 86400e3)) return;
    (g.props || []).forEach((p) => { if (p && p.id && ["QB", "RB", "WR", "TE"].includes(p.pos)) { ids.add(String(p.id)); pos[String(p.id)] = p.pos; } });
  });
  const want = [...ids].filter((id) => !skip.includes(id));
  const yr = new Date().getFullYear();
  const out = {};
  let cursor = 0;
  async function worker() {
    while (cursor < want.length) {
      const id = want[cursor++];
      const rows = [];
      for (const y of [yr, yr - 1]) {
        try {
          const d = await getJSON("https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/" + id + "/gamelog?season=" + y);
          parseGamelog(d, y).forEach((r) => rows.push(r));
        } catch (e) {}
      }
      const seen = new Set();
      out[id] = rows.filter((r) => !seen.has(r.id) && seen.add(r.id))
        .sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 17);
    }
  }
  await Promise.all([worker(), worker(), worker(), worker(), worker(), worker()]);
  return { all: [...ids], got: out, pos };
}
"""


async def run(skip):
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
        res = await page.evaluate(JS, skip)
        await browser.close()
        return res


def main():
    now = datetime.now(timezone.utc)
    try:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        old = {}
    players = old.get("players") or {}
    fresh = [pid for pid, v in players.items() if v.get("at") and now - datetime.fromisoformat(v["at"].replace("Z", "+00:00")) < timedelta(hours=20)]
    res = asyncio.run(run(fresh))
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    got = 0
    for pid, rows in (res.get("got") or {}).items():
        if not rows:
            continue
        slim = []
        for r in rows:
            row = {"d": (r.get("date") or "")[:10], "o": r.get("opp") or "", "s": r.get("season")}
            for k in KEEP:
                if r.get(k) is not None:
                    row[k] = r[k]
            slim.append(row)
        players[pid] = {"at": stamp, "rows": slim}
        got += 1
    for pid, ps in (res.get("pos") or {}).items():   # position, for the matchup ranks
        if pid in players and ps:
            players[pid]["pos"] = ps
    on_board = set(res.get("all") or [])
    for pid in list(players):
        if pid in on_board:
            continue
        try:
            stale = now - datetime.fromisoformat(players[pid]["at"].replace("Z", "+00:00")) > timedelta(days=14)
        except Exception:
            stale = True
        if stale:
            del players[pid]
    OUT.write_text(json.dumps({"updated": stamp, "players": players}, separators=(",", ":")) + "\n")
    print(f"{len(on_board)} players on the board; fetched {got}; {len(players)} in the file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
