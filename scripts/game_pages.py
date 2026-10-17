#!/usr/bin/env python3
"""A page and a share image for every game, for search and for links people share.

Opens this checkout's own index.html in headless Chromium (internet allowed, like
scripts/gameday.py), lets the board settle, and reads every game from three days ago to nine
days ahead: teams, kickoff, the line, our projected score and win chances, the pick (a real
play, a lean, or none), weather and the main injuries, and the final when there is one.
The numbers are the page's own, so a game page always matches the site.

For each game it writes
  g/<slug>/index.html  a small, fast page: title and description made for search, the
                       projection and pick in plain HTML, SportsEvent structured data, and a
                       link into the full game on Double Gs
  g/<slug>/card.jpg    a 1200x630 share image, drawn from an HTML card in the same browser
                       with the site's fonts; redrawn only when the card's text changes
and keeps data/game-pages.json (what was drawn) and sitemap.xml up to date. Pages for games
more than three weeks old are removed.
slug: <league>-<season>-w<week>-<away>-at-<home>-<id>, e.g. nfl-2026-w6-car-at-phi-401872998
Usage: python3 scripts/game_pages.py
"""
import asyncio
import hashlib
import html
import json
import mimetypes
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
OUT = ROOT / "g"
INDEX = ROOT / "data" / "game-pages.json"
SITEMAP = ROOT / "sitemap.xml"
ET = ZoneInfo("America/New_York")
BLOCK = {"corsproxy.io", "api.allorigins.win", "fonts.googleapis.com", "fonts.gstatic.com"}

READ = """
() => {
  const now = Date.now();
  const lab = (lg, w) => (typeof weekLabel === "function" ? weekLabel(lg, w) : (lg === "nfl" ? "NFL Week " : "College Week ") + w);
  return (DATA.games || []).filter((g) => (g.league === "nfl" || g.league === "cfb") && g.date && g.home && g.away
      && Date.parse(g.date) > now - 3 * 86400e3 && Date.parse(g.date) < now + 9 * 86400e3)
    .map((g) => {
      const p = g.proj || {}, o = g.odds || {};
      const sp = typeof shownPick === "function" ? shownPick(g) : {};
      const lean = g.league === "cfb" && typeof cfbListedPick === "function" ? cfbListedPick(g) : {};
      const realSide = p.pick && p.pick !== "NO PLAY" ? (p.pick_line || p.pick) : null;
      const realTot = p.total_pick && p.total_pick !== "NO PLAY" ? p.total_pick : null;
      const team = (t) => ({ abbr: t.abbr || "", name: t.name || "", logo: t.logo || "", record: t.record || "", rank: t.rank || null, score: t.score });
      const out = (g.injuries || []).filter((r) => /OUT|DOUBT/.test(String(r.tag || r.status || "").toUpperCase())).slice(0, 4)
        .map((r) => ({ name: r.name, pos: r.pos || "", tag: r.tag || r.status, team: r.side === "home" ? g.home.abbr : g.away.abbr }));
      const wx = g.weather || {};
      return {
        id: String(g.id), league: g.league, week: Number(g.week) || 0, weekLabel: lab(g.league, Number(g.week) || 0),
        date: g.date, venue: g.venue || "", city: [g.city, g.state].filter(Boolean).join(", "), tv: (g.broadcasts || [])[0] || "",
        away: team(g.away), home: team(g.home), completed: !!g.completed,
        line: o.details || "", total: o.total != null ? Number(o.total) : null,
        awayPts: p.away_points != null ? Number(p.away_points) : null, homePts: p.home_points != null ? Number(p.home_points) : null,
        winHome: p.win_prob_home != null ? Number(p.win_prob_home) : null,
        side: sp.side || realSide || null, tot: sp.total || realTot || null, locked: !!(sp && sp.lock),
        leanSide: !realSide && lean.pick_line ? lean.pick_line : null, leanTot: !realTot && lean.total_pick && lean.total_pick !== "NO PLAY" ? lean.total_pick : null,
        chance: typeof playChance === "function" ? (Number(playChance(g)) || null) : null,
        why: (typeof cfbPickWhy === "function" && g.league === "cfb" ? cfbPickWhy(g) : ((g.situational || {}).notes || [])).slice(0, 3),
        weather: g.indoor ? "Indoors" : (wx.temp_f != null ? `${wx.condition || "Outdoor"}, ${Math.round(wx.temp_f)}°F, wind ${Math.round(wx.wind_mph || 0)} mph` : ""),
        injuries: out
      };
    });
}
"""


def slug_of(g):
    s = f"{g['league']}-2026-w{g['week']}-{g['away']['abbr']}-at-{g['home']['abbr']}-{g['id']}".lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def kick_et(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    return d.strftime("%A, %B ") + str(d.day) + ", " + d.strftime("%I:%M %p").lstrip("0") + " ET"


def r1(x):
    return "—" if x is None else f"{x:.1f}"


def pick_text(g):
    if g["side"] or g["tot"]:
        return " · ".join(x for x in (g["side"], g["tot"]) if x), "Our pick" + (" (locked)" if g["locked"] else "")
    if g["leanSide"] or g["leanTot"]:
        return " · ".join(x for x in (g["leanSide"], g["leanTot"]) if x), "Lean only, not a play"
    return "No play", "Too close to call"


_FONTS = {}


def FONT64(name):
    import base64
    if name not in _FONTS:
        _FONTS[name] = base64.b64encode((ROOT / "assets" / "fonts" / name).read_bytes()).decode()
    return _FONTS[name]


def card_html(g):
    pick, pick_lbl = pick_text(g)
    final = g["completed"] and g["away"]["score"] not in (None, "")
    whole = lambda x: "—" if x is None else str(int(round(x)))
    a_num = g["away"]["score"] if final else whole(g["awayPts"])
    h_num = g["home"]["score"] if final else whole(g["homePts"])
    head = "Final" if final else "Projected score"
    font = lambda n: "data:font/woff2;base64," + FONT64(n)
    logo = lambda t: (f'<img src="{esc(t["logo"])}" alt="" onerror="this.replaceWith(Object.assign(document.createElement(\'div\'),{{className:\'nologo\',textContent:\'{esc(t["abbr"][:3])}\'}}))">'
                      if t["logo"] else f'<div class="nologo">{esc(t["abbr"][:3])}</div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:BS;src:url({font('big-shoulders-800.woff2')});font-weight:800}}
@font-face{{font-family:B;src:url({font('barlow-600.woff2')});font-weight:600}}
@font-face{{font-family:B;src:url({font('barlow-800.woff2')});font-weight:800}}
html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}
body{{background:radial-gradient(900px 500px at 85% -10%,rgba(227,168,62,.22),transparent 60%),linear-gradient(160deg,#0a1a12,#0f2a1e 55%,#14301f);color:#f1ede1;font-family:B;}}
.wrap{{position:absolute;inset:44px 56px}}
.top{{display:flex;justify-content:space-between;align-items:center;font-weight:800;font-size:26px;color:#f4cb72;letter-spacing:.02em}}
.brand{{display:flex;align-items:center;gap:14px}} .mark{{background:linear-gradient(160deg,#f4cb72,#c98a22);color:#261803;font-family:BS;font-size:30px;padding:4px 12px;border-radius:10px}}
.when{{color:#c5d6c9;font-weight:600;font-size:24px}}
.teams{{display:grid;grid-template-columns:330px 1fr 330px;align-items:center;margin-top:40px}}
.t{{display:flex;align-items:center;gap:20px;min-width:0}} .t.home{{justify-content:flex-end;text-align:right}}
.t img,.nologo{{width:112px;height:112px;object-fit:contain;flex:none}} .nologo{{display:grid;place-items:center;border-radius:50%;background:#1c4231;font-family:BS;font-size:40px}}
.ab{{font-family:BS;font-size:84px;line-height:.9}} .nm{{font-size:22px;color:#c5d6c9;font-weight:600;line-height:1.15;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.score{{font-family:BS;font-size:150px;line-height:.9;color:#f4cb72;text-align:center;white-space:nowrap}}
.score span{{color:#6b7d70;font-size:90px;padding:0 14px;vertical-align:middle}}
.lbl{{text-align:center;color:#8aa090;font-weight:800;font-size:22px;letter-spacing:.14em;text-transform:uppercase;margin-top:6px}}
.wins{{text-align:center;color:#c5d6c9;font-weight:600;font-size:28px;margin-top:22px}}
.bottom{{position:absolute;left:0;right:0;bottom:0;display:flex;gap:18px}}
.box{{flex:1;background:rgba(21,53,38,.85);border:2px solid rgba(227,168,62,.32);border-radius:18px;padding:16px 22px}}
.box b{{display:block;font-family:BS;font-size:46px;line-height:1;color:#f1ede1}} .box small{{color:#8aa090;font-size:20px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}}
.box.pick{{flex:1.5;border-color:#f4cb72}} .box.pick b{{color:#f4cb72}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><span class="mark">GG</span>Double Gs · {esc(g['weekLabel'])}</div><div class="when">{esc(kick_et(g['date']))}</div></div>
<div class="teams">
  <div class="t">{logo(g['away'])}<div><div class="ab">{esc(g['away']['abbr'])}</div><div class="nm">{esc(g['away']['name'])}</div></div></div>
  <div class="score">{esc(a_num)}<span>–</span>{esc(h_num)}</div>
  <div class="t home"><div><div class="ab">{esc(g['home']['abbr'])}</div><div class="nm">{esc(g['home']['name'])}</div></div>{logo(g['home'])}</div>
</div>
<div class="lbl">{head}</div>
{'' if final or g['winHome'] is None else f'<div class="wins">{esc(g["away"]["abbr"])} {round((1 - g["winHome"]) * 100)}% to win · {esc(g["home"]["abbr"])} {round(g["winHome"] * 100)}%</div>'}
<div class="bottom">
  <div class="box"><small>Line</small><b>{esc(g['line'] or '—')}</b></div>
  <div class="box"><small>Total</small><b>{esc(r1(g['total']) if g['total'] is not None else '—')}</b></div>
  <div class="box pick"><small>{esc(pick_lbl)}</small><b>{esc(pick)}</b></div>
</div></div></body></html>"""


def page_html(g, slug, img_ver):
    a, h = g["away"], g["home"]
    pick, pick_lbl = pick_text(g)
    final = g["completed"] and a["score"] not in (None, "")
    url = f"{SITE}/g/{slug}/"
    title = f"{a['name']} vs {h['name']} Prediction, {g['weekLabel']}: Projected Score and Pick | Double Gs"
    proj = f"{a['abbr']} {r1(g['awayPts'])}, {h['abbr']} {r1(g['homePts'])}" if g["awayPts"] is not None else ""
    desc = (f"Final: {a['abbr']} {a['score']}, {h['abbr']} {h['score']}. " if final else "") + \
           (f"Our projection: {proj}. " if proj else "") + \
           (f"Line {g['line']}" + (f", total {r1(g['total'])}" if g['total'] is not None else "") + ". " if g["line"] else "") + \
           f"{pick_lbl}: {pick}. Weather, injuries and every book's price on Double Gs."
    win_h = g["winHome"]
    wins = f"{a['abbr']} {round((1 - win_h) * 100)}% · {h['abbr']} {round(win_h * 100)}%" if win_h is not None else "—"
    ld = {
        "@context": "https://schema.org", "@type": "SportsEvent",
        "name": f"{a['name']} at {h['name']}", "startDate": g["date"], "url": url,
        "sport": "American football", "eventStatus": "https://schema.org/EventScheduled",
        "awayTeam": {"@type": "SportsTeam", "name": a["name"]}, "homeTeam": {"@type": "SportsTeam", "name": h["name"]},
        "competitor": [{"@type": "SportsTeam", "name": a["name"]}, {"@type": "SportsTeam", "name": h["name"]}],
        "location": {"@type": "Place", "name": g["venue"] or h["name"], "address": g["city"] or ""},
        "image": f"{url}card.jpg?v={img_ver}", "description": desc,
    }
    rows = [("Kickoff", kick_et(g["date"]) + (f" · {g['tv']}" if g["tv"] else "")),
            ("Where", ", ".join(x for x in (g["venue"], g["city"]) if x) or "—"),
            ("The line", (g["line"] or "No line yet") + (f" · total {r1(g['total'])}" if g["total"] is not None else "")),
            ("Win chances", wins)]
    if g["weather"]:
        rows.append(("Weather", g["weather"]))
    inj = "; ".join(f"{i['name']} ({i['team']} {i['pos']}) {str(i['tag']).lower()}" for i in g["injuries"])
    if inj:
        rows.append(("Key injuries", inj))
    why = "".join(f"<li>{esc(w)}</li>" for w in g["why"] if w)
    split = f'<a class="btn alt" href="/split/#{esc(g["id"])}">Open the matchup sheet</a>' if g["league"] == "cfb" else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon-48.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0f2a1e">
<meta property="og:type" content="article"><meta property="og:site_name" content="Double Gs">
<meta property="og:url" content="{url}"><meta property="og:title" content="{esc(a['abbr'])} at {esc(h['abbr'])}: {esc(proj or 'our projection')} | Double Gs">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{url}card.jpg?v={img_ver}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(a['name'])} at {esc(h['name'])}: projected score and pick">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{url}card.jpg?v={img_ver}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
<style>
@font-face{{font-family:BS;src:url(/assets/fonts/big-shoulders-800.woff2) format("woff2");font-weight:800;font-display:swap}}
@font-face{{font-family:B;src:url(/assets/fonts/barlow-400.woff2) format("woff2");font-weight:400;font-display:swap}}
@font-face{{font-family:B;src:url(/assets/fonts/barlow-800.woff2) format("woff2");font-weight:800;font-display:swap}}
:root{{--bg:#0f2a1e;--card:#153526;--line:rgba(227,168,62,.22);--ink:#f1ede1;--soft:#c5d6c9;--muted:#8aa090;--sun:#f4cb72}}
*{{box-sizing:border-box}} html,body{{margin:0;background:var(--bg);color:var(--ink);font-family:B,system-ui,sans-serif;line-height:1.5}}
main{{max-width:760px;margin:0 auto;padding:20px 16px 48px}}
header{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}}
.brand{{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-family:BS;font-size:26px}}
.mark{{background:linear-gradient(160deg,#f4cb72,#c98a22);color:#261803;padding:2px 9px;border-radius:9px}}
.kicker{{color:var(--sun);font-weight:800;font-size:14px;letter-spacing:.06em}}
h1{{font-family:BS;font-size:clamp(30px,7vw,48px);line-height:1.02;margin:6px 0 14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px}}
.score{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;text-align:center;gap:8px}}
.score img{{width:64px;height:64px;object-fit:contain}} .score b{{display:block;font-family:BS;font-size:30px}}
.score .num{{font-family:BS;font-size:clamp(48px,14vw,84px);color:var(--sun);white-space:nowrap}}
.score small{{color:var(--muted)}} .lbl{{text-align:center;color:var(--muted);font-weight:800;font-size:13px;letter-spacing:.1em;text-transform:uppercase}}
.pick{{margin-top:14px;padding:14px 16px;border:1.5px solid var(--sun);border-radius:14px}}
.pick span{{color:var(--muted);font-weight:800;font-size:13px}} .pick strong{{display:block;font-family:BS;font-size:30px;color:var(--sun)}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;margin:16px 0 0}} dt{{color:var(--muted)}} dd{{margin:0}}
ul{{padding-left:20px;color:var(--soft)}}
.btns{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}
.btn{{background:var(--sun);color:#261803;text-decoration:none;font-weight:800;padding:12px 18px;border-radius:12px}}
.btn.alt{{background:transparent;color:var(--sun);border:1px solid rgba(244,203,114,.5)}}
.btn:focus-visible{{outline:3px solid var(--ink);outline-offset:2px}}
.fine{{color:var(--muted);font-size:13px;margin-top:22px}}
</style></head><body><main>
<header><a class="brand" href="/#home"><span class="mark">GG</span>Double Gs</a><span class="kicker">{esc(g['weekLabel'])}</span></header>
<div class="kicker">{'Final' if final else 'Prediction'}</div>
<h1>{esc(a['name'])} at {esc(h['name'])}</h1>
<section class="card">
  <div class="score">
    <div>{f'<img src="{esc(a["logo"])}" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">' if a['logo'] else ''}<b>{esc(a['abbr'])}</b><small>{esc(a['record'])}</small></div>
    <div class="num">{esc(a['score'] if final else r1(g['awayPts']))} – {esc(h['score'] if final else r1(g['homePts']))}</div>
    <div>{f'<img src="{esc(h["logo"])}" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">' if h['logo'] else ''}<b>{esc(h['abbr'])}</b><small>{esc(h['record'])}</small></div>
  </div>
  <div class="lbl">{'Final score' if final else 'Our projected score'}</div>
  <div class="pick"><span>{esc(pick_lbl)}</span><strong>{esc(pick)}</strong>{f'<span>{esc(g["chance"])}% to hit, checked against this season</span>' if g.get('chance') and (g['side'] or g['tot']) else ''}</div>
  <dl>{''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in rows)}</dl>
  {f'<h2 style="font-family:BS;font-size:24px;margin:18px 0 4px">Why</h2><ul>{why}</ul>' if why else ''}
</section>
<div class="btns"><a class="btn" href="/#game-{esc(g['id'])}">Open the full game on Double Gs</a>{split}<a class="btn alt" href="/#{esc(g['league'])}">All {'NFL' if g['league'] == 'nfl' else 'college'} games</a></div>
<p class="fine">Projections are for information and entertainment, not betting advice. Every pick is graded on the public <a href="/#score" style="color:var(--soft)">scorecard</a>.</p>
</main></body></html>
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
            from urllib.parse import urlparse
            if (urlparse(url).hostname or "") in BLOCK or r.request.resource_type in ("font", "media"):
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
        page.on("pageerror", lambda e: print("page error:", str(e)[:200]))
        await page.goto(SITE + "/#home", wait_until="load", timeout=120000)
        await page.wait_for_function("typeof DATA !== 'undefined' && DATA && (DATA.games || []).length > 0", timeout=120000)
        await page.wait_for_timeout(12000)  # finals, injuries, weather and the board settle
        games = await page.evaluate(READ)

        try:
            index = json.loads(INDEX.read_text()) if INDEX.exists() else {}
        except Exception:
            index = {}
        shot = await browser.new_page(viewport={"width": 1200, "height": 630})
        drawn = written = 0
        now = datetime.now(timezone.utc)
        for g in games:
            if g["awayPts"] is None and not g["completed"]:
                continue
            slug = slug_of(g)
            folder = OUT / slug
            folder.mkdir(parents=True, exist_ok=True)
            card = card_html(g)
            fp = hashlib.sha1(card.encode()).hexdigest()[:12]
            prev = index.get(slug) or {}
            if prev.get("fp") != fp or not (folder / "card.jpg").exists():
                await shot.set_content(card, wait_until="load")
                await shot.wait_for_timeout(300)
                await shot.screenshot(path=str(folder / "card.jpg"), type="jpeg", quality=82)
                drawn += 1
            page_text = page_html(g, slug, fp)
            target = folder / "index.html"
            if not target.exists() or target.read_text(encoding="utf-8") != page_text:
                target.write_text(page_text, encoding="utf-8")
                written += 1
            index[slug] = {"id": g["id"], "league": g["league"], "date": g["date"], "fp": fp,
                           "seen": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        await browser.close()

    # drop pages for games more than three weeks old
    cutoff = now - timedelta(days=21)
    for slug, row in list(index.items()):
        try:
            old = datetime.fromisoformat(row["date"].replace("Z", "+00:00")) < cutoff
        except Exception:
            old = False
        if old:
            shutil.rmtree(OUT / slug, ignore_errors=True)
            del index[slug]
    INDEX.write_text(json.dumps(index, indent=0, sort_keys=True) + "\n")

    urls = [f"{SITE}/", f"{SITE}/split/"] + [f"{SITE}/g/{s}/" for s in sorted(index, key=lambda s: index[s]["date"], reverse=True)]
    lastmod = lambda u: (index.get(u.rstrip("/").split("/g/")[-1]) or {}).get("seen", now.strftime("%Y-%m-%dT%H:%M:%SZ"))[:10]
    SITEMAP.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                       "".join(f"  <url><loc>{u}</loc><lastmod>{lastmod(u)}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    print(f"{len(games)} games read; {written} pages written, {drawn} share images drawn; {len(index)} pages in all")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
