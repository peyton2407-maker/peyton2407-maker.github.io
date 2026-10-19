#!/usr/bin/env python3
"""Live weather and injury reports for every visitor, run on the server, on a schedule.

The site's weather (Open-Meteo at each stadium) and injury reports (ESPN, Sleeper and
reporters for the NFL, Covers for college) used to be pulled only inside a visitor's
browser, so they went stale whenever nobody had the page open. This opens this checkout's
own index.html in headless Chromium with internet access, runs the site's own code
(attachWeather, fetchInjuries, runDueWeatherReports) so the numbers match the page exactly,
and saves:
  data/eleven.json          today's latest report the page installs on start and every few
                            minutes after: NFL and college injuries, weather for every
                            upcoming game
  data/reports/day-<ymd>.json   each finished day's last report, so the week's day-by-day
                            history (Wed, Thu, Fri...) is there for every visitor
  data/reports/kick.json    the NFL reports taken 90 minutes before each kickoff (injuries for
                            both teams and the forecast), updated until 30 minutes after kick
  data/snapshot.json        (--snapshot-only) each upcoming game's forecast for first paint
Requests leave from the server, so Covers is read directly (no relay).

Usage:
  python3 scripts/gameday.py                  # the reports (scheduled every 15 minutes)
  python3 scripts/gameday.py --due            # prints run=yes/run=no: is a report due now?
  python3 scripts/gameday.py --snapshot-only  # forecasts into data/snapshot.json (hourly refresh)
  python3 scripts/gameday.py --watch          # exits 1 when a visitor would see stale reports
"""
import asyncio
import hashlib
import json
import mimetypes
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://peyton2407-maker.github.io"
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "eleven.json"
REPORTS = ROOT / "data" / "reports"
KICK = REPORTS / "kick.json"
ET = ZoneInfo("America/New_York")
BLOCK = {"corsproxy.io", "api.allorigins.win", "www.googletagmanager.com", "fonts.googleapis.com", "fonts.gstatic.com"}

JS = """
async (mode) => {
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
  if (mode === "snapshot") return out;
  const clean = (rows) => JSON.parse(JSON.stringify((rows || []).map((r) => {
    const o = {}; Object.keys(r).forEach((k) => { if (!k.startsWith("_")) o[k] = r[k]; }); return o;
  })));
  try { view = "cfbinj"; await fetchInjuries(true); const p = ensureInjPack(); out.cfb = clean(p.cfb); out.cfbSource = p.cfbLive || ""; }
  catch (e) { out.notes.push("cfb injuries: " + e); }
  try { view = "nflinj"; await fetchInjuries(true); const p = ensureInjPack(); out.nfl = clean(p.nfl); }
  catch (e) { out.notes.push("nfl injuries: " + e); }
  // reports due now (90 minutes before each NFL kickoff): injuries were saved by
  // fetchInjuries above; the forecasts by the page's own weather report runner
  try { if (typeof runDueWeatherReports === "function") await runDueWeatherReports(); }
  catch (e) { out.notes.push("weather reports: " + e); }
  const kicks = (all) => { const o = {}; Object.keys(all || {}).forEach((k) => { if (k.startsWith("ko-") && ((all[k] || {}).rows || []).length) o[k] = all[k]; }); return o; };
  try { out.kickNfl = JSON.parse(JSON.stringify(kicks(loadNflInjReports()))); } catch (e) { out.kickNfl = {}; }
  try { out.kickWx = JSON.parse(JSON.stringify(kicks(loadWxReports()))); } catch (e) { out.kickWx = {}; }
  out.et = etFields();
  return out;
}
"""


async def run(mode="reports"):
    # imported here: --due and --watch run before the browser is installed
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
        out = await page.evaluate(JS, mode)
        await browser.close()
        return out


def parse(t):
    try:
        t = str(t).replace("Z", "+00:00")
        if len(t) == 22:  # "2026-10-18T20:05+00:00"
            t = t[:16] + ":00" + t[16:]
        return datetime.fromisoformat(t)
    except Exception:
        return None


def load(path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def due(now=None):
    """Is a report due? Kickoff windows (90 minutes before an NFL or college kickoff to 30
    after), the 11:00 AM ET report, or the last report is about an hour old."""
    now = now or datetime.now(timezone.utc)
    old = load(OUT, {})
    saved = datetime.fromtimestamp((old.get("saved") or 0) / 1000, timezone.utc)
    if now - saved > timedelta(minutes=50):
        return "last report is %d minutes old" % ((now - saved).total_seconds() // 60)
    et = now.astimezone(ET)
    eleven = et.replace(hour=11, minute=0, second=0, microsecond=0)
    if et >= eleven and saved.astimezone(ET) < eleven:
        return "11:00 AM ET report"
    for g in load(SNAP, {}).get("games") or []:
        if g.get("league") not in ("nfl", "cfb") or g.get("completed"):
            continue
        k = parse(g.get("date"))
        if k and k - timedelta(minutes=100) <= now <= k + timedelta(minutes=30):
            return "kickoff window: " + str(g.get("short_name"))
    return None


def snapshot_weather(out):
    if not out.get("wx"):
        return
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


def content_hash(r):
    return hashlib.md5(json.dumps({k: r.get(k) for k in ("nfl", "cfb", "wxNfl", "wxCfb")}, sort_keys=True).encode()).hexdigest()


def watch(now=None):
    """Problems a visitor would notice. A non-empty list fails the scheduled job, and GitHub
    emails the repository owner about a failed scheduled run."""
    now = now or datetime.now(timezone.utc)
    bad = []
    old = load(OUT, {})
    age = now - datetime.fromtimestamp((old.get("saved") or 0) / 1000, timezone.utc)
    if age > timedelta(hours=3):
        bad.append(f"injury and weather report is {age.total_seconds() / 3600:.1f} hours old")
    kick = load(KICK, {})
    games = load(SNAP, {}).get("games") or []
    started = datetime.fromtimestamp(min([x.get("saved") or 9e15 for x in (kick.get("nfl") or {}).values()] or [9e15]) / 1000, timezone.utc) if kick.get("nfl") else now
    for g in games:
        k = parse(g.get("date"))
        if g.get("league") != "nfl" or not k or not (now - timedelta(hours=24) < k < now - timedelta(minutes=45)):
            continue
        if k < started:  # before the server took kickoff reports
            continue
        if not (kick.get("nfl") or {}).get("ko-" + str(g.get("id"))):
            bad.append(f"no kickoff injury report for {g.get('short_name')}")
    outdoor = [g for g in games if not g.get("completed") and not g.get("indoor") and g.get("league") in ("nfl", "cfb")
               and parse(g.get("date")) and now < parse(g["date"]) < now + timedelta(days=3)]
    nowx = [g.get("short_name") for g in outdoor if not g.get("weather")]
    if outdoor and len(nowx) > max(2, len(outdoor) // 10):
        bad.append(f"{len(nowx)} of {len(outdoor)} outdoor games in the next 3 days have no forecast: {', '.join(nowx[:6])}")
    return bad


def main():
    args = sys.argv[1:]
    if "--watch" in args:
        bad = watch()
        for b in bad:
            print("PROBLEM:", b)
        print("all reports fresh" if not bad else f"{len(bad)} problem(s)")
        return 1 if bad else 0
    if "--due" in args:
        why = due()
        print("run=yes" if why else "run=no")
        print("why:", why or "nothing due", file=sys.stderr)
        return 0
    mode = "snapshot" if "--snapshot-only" in args else "reports"
    out = asyncio.run(run(mode))
    now = datetime.now(timezone.utc)
    print(f"{out.get('games')} upcoming games, weather for {len(out['wx'])}")
    for n in out.get("notes") or []:
        print("note:", n)
    if mode == "snapshot":
        snapshot_weather(out)
        return 0
    et = out.get("et") or {}
    print(f"injuries: {len(out['nfl'])} NFL, {len(out['cfb'])} college ({out.get('cfbSource') or 'no source'})")

    # 1) the latest report the page installs on load
    old = load(OUT, {})
    today = et.get("ymd") or now.astimezone(ET).strftime("%Y-%m-%d")
    fresh_old = old.get("ymd") == today
    # a new day: the old report is that day's last word; keep it for the week's history
    if old.get("ymd") and not fresh_old:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"day-{old['ymd']}.json").write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")) + "\n")
        print("archived", old["ymd"])
    hour = int(et.get("hour") or 0)
    label = f"Updated {hour % 12 or 12}:{int(et.get('minute') or 0):02d} {'PM' if hour >= 12 else 'AM'} ET"
    report = {
        "ymd": today,
        "weekday": et.get("weekday") or now.astimezone(ET).strftime("%a"),
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
    elif fresh_old and content_hash(report) == content_hash(old) and now.timestamp() * 1000 - (old.get("saved") or 0) < 50 * 60 * 1000:
        print("Report unchanged; not rewritten.")
    else:
        OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")

    # old day files (the page shows a week)
    if REPORTS.exists():
        for f in REPORTS.glob("day-*.json"):
            try:
                if (now.date() - datetime.strptime(f.stem[4:], "%Y-%m-%d").date()).days > 10:
                    f.unlink()
            except Exception:
                pass

    # 2) kickoff reports: replaced while their window is open, then left as they were
    kick = load(KICK, {"nfl": {}, "wx": {}})
    changed = False
    for part, got in (("nfl", out.get("kickNfl") or {}), ("wx", out.get("kickWx") or {})):
        bag = kick.setdefault(part, {})
        for k, v in got.items():
            if bag.get(k, {}).get("rows") != v.get("rows"):
                bag[k] = v
                changed = True
        for k in list(bag):  # a week and a half is all the page shows
            if now.timestamp() * 1000 - (bag[k].get("saved") or 0) > 10 * 86400 * 1000:
                del bag[k]
                changed = True
    # which finished days have a saved report, so the page asks only for those
    days = sorted(f.stem[4:] for f in REPORTS.glob("day-*.json")) if REPORTS.exists() else []
    if kick.get("days") != days:
        kick["days"] = days
        changed = True
    if changed:
        REPORTS.mkdir(parents=True, exist_ok=True)
        KICK.write_text(json.dumps(kick, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"kickoff reports: {len(kick.get('nfl') or {})} injury, {len(kick.get('wx') or {})} weather")
    return 0


if __name__ == "__main__":
    sys.exit(main())
