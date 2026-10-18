#!/usr/bin/env python3
"""Capture what a visitor sees on one page of the live site: screenshot, text and, for the
props page, every card's numbers next to the player's real recent games. For checking pages
that load live data (ESPN, the books) from outside. Writes probe-out/.
Usage: python3 scripts/page_probe.py props
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SITE = "https://peyton2407-maker.github.io"
OUT = Path("probe-out")

PROPS_DIAG = """() => {
  const rows = (typeof collectNflProps === 'function' ? collectNflProps() : []);
  const now = Date.now();
  const games = (DATA.games || []).filter((g) => g.league === 'nfl' && !g.completed && Date.parse(g.date) > now - 4 * 3600e3)
    .map((g) => ({ id: g.id, short: g.short_name, date: g.date, week: g.week, props: (g.props || []).length, dk: !!(window.__DK && window.__DK[String(g.id)] && window.__DK[String(g.id)].__listed) }));
  const cards = [...document.querySelectorAll('#propBoard .prop-card')].map((el) => {
    const p = rows.find((r) => String(r.id) === el.dataset.player && String(r.game_id) === el.dataset.id) || {};
    const lean = typeof postedLean === 'function' ? postedLean(Object.assign({}, p)) : null;
    const logs = (window.GAMELOGS || {})[String(p.id)];
    const recent = logs ? (logs.rows || []).slice(0, 6).map((r) => ({ d: r.d, o: r.o, pass_yds: r.pass_yds, pass_td: r.pass_td, rush_yds: r.rush_yds, rec: r.rec, rec_yds: r.rec_yds })) : null;
    return { text: el.innerText.replace(/\\s+/g, ' ').slice(0, 400), name: p.name, pos: p.pos, team: p.team, opp: p.opp, game: p.game, date: p.date, injury: p.injury,
      proj: { pass_yds: p.pass_yds, pass_td: p.pass_td, rush_yds: p.rush_yds, rush_att: p.rush_att, rec: p.rec, rec_yds: p.rec_yds, rec_td: p.rec_td, rush_td: p.rush_td, fp: p.fp },
      lean: lean ? { stat: lean.m.key, line: lean.line, take: lean.take, chance: +lean.chance.toFixed(3), mean: lean.m.mean } : null, recent };
  });
  return { now: new Date().toISOString(), view, games, total_props: rows.length,
    controls: [...document.querySelectorAll('#propsSection select')].map((s) => ({ id: s.id, value: s.value, options: [...s.options].map((o) => o.value + '=' + o.text) })),
    stats: (document.getElementById('propStats') || {}).innerText, cards };
}"""


async def main(view):
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, vp in (("desktop", {"width": 1280, "height": 900}), ("phone", {"width": 390, "height": 844})):
            ctx = await browser.new_context(viewport=vp)
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:300]))
            page.on("console", lambda m: m.type in ("error", "warning") and len(errors) < 80 and errors.append(m.type + ": " + m.text[:200]))
            await page.goto(SITE + "/#" + view, wait_until="load", timeout=120000)
            await page.wait_for_timeout(60000)
            await page.screenshot(path=str(OUT / f"{view}-{name}.png"), full_page=False)
            await page.screenshot(path=str(OUT / f"{view}-{name}-full.png"), full_page=True)
            text = await page.evaluate("(document.querySelector('main') || document.body).innerText")
            (OUT / f"{view}-{name}.txt").write_text(text)
            if name == "desktop":
                diag = await page.evaluate(PROPS_DIAG) if view == "props" else {}
                diag["errors"] = errors
                (OUT / f"{view}-diag.json").write_text(json.dumps(diag, indent=1))
            await ctx.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "props"))
