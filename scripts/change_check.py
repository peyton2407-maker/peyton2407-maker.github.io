#!/usr/bin/env python3
"""After a change to the site's code or the picks: open every page of this checkout in a real
browser (desktop and phone size) with the internet blocked, so it tests the commit itself with
the data saved in the repo, and fail on anything a visitor would see break: a script error, a
page with nothing on it, "NaN"/"undefined" in the text, a page wider than the phone, or a script
that doesn't parse. Writes check-out/report.json and prints a summary. Exit 1 on a failure.

Usage: python3 scripts/change_check.py [repo dir]
"""
import asyncio
import json
import mimetypes
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
HOST = "https://peyton2407-maker.github.io"
OUT = ROOT / "check-out"
VIEWS = ["home", "card", "nflpotd", "potd", "ladder", "nfl", "prime", "props", "tds", "value", "live", "charts", "nflwx", "nflinj",
         "cfb", "cfbpicks", "cfbwx", "cfbinj", "all", "score", "history", "season", "ratings", "bets", "builder", "parlay", "calc", "create"]
# words in the page text that mean a number or field didn't fill in
LEAK = re.compile(r"\bNaN\b|\bundefined\b|\[object Object\]|\bInfinity\b")
# console noise from the blocked internet, not from the page
NOISE = re.compile(r"Failed to load resource|net::ERR_|ERR_FAILED|ERR_BLOCKED|CORS|Access to fetch|TypeError: Failed to fetch|NetworkError|Load failed|ERR_NAME_NOT_RESOLVED")
CHECK = """() => {
  const root = document.querySelector('main') || document.body;
  const text = root.innerText || '';
  const leaks = [];
  const re = /\\bNaN\\b|\\bundefined\\b|\\[object Object\\]|\\bInfinity\\b/g;
  let m; while ((m = re.exec(text)) && leaks.length < 5) leaks.push(text.slice(Math.max(0, m.index - 60), m.index + 30).replace(/\\s+/g, ' '));
  return { view: typeof view !== 'undefined' ? view : null, chars: text.trim().length, leaks, wide: document.documentElement.scrollWidth - innerWidth };
}"""


def syntax():
    """Every inline script in index.html and the other pages parses."""
    bad = []
    for page in [ROOT / "index.html", ROOT / "split" / "index.html", ROOT / "boom.html", ROOT / "hashmark.html"]:
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        scripts = re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*type=\"application/(?:ld\+)?json\")[^>]*>([\s\S]*?)</script>", html)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write("\n;\n".join(scripts))
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        if r.returncode:
            lines = r.stderr.strip().splitlines()
            msg = next((l for l in lines if "Error" in l), "does not parse").strip()
            src = next((l.strip() for i, l in enumerate(lines) if i and lines[i - 1].startswith(f.name)), "")
            bad.append(f"{page.relative_to(ROOT)} doesn't parse: {msg[:160]}" + (f" near \"{src[:80]}\"" if src else ""))
    return bad


async def route(r):
    url = r.request.url
    if not url.startswith(HOST):
        return await r.abort()
    path = url[len(HOST):].split("?")[0].split("#")[0] or "/"
    f = ROOT / path.lstrip("/")
    if f.is_dir():
        f = f / "index.html"
    if not f.exists() and not f.suffix and (ROOT / (path.lstrip("/") + ".html")).exists():
        f = ROOT / (path.lstrip("/") + ".html")
    if not f.exists():
        return await r.fulfill(status=404, body=b"not found")
    ct = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
    if ct.startswith("text/") or ct in ("application/json", "application/javascript", "image/svg+xml"):
        ct += "; charset=utf-8"
    return await r.fulfill(status=200, body=f.read_bytes(), headers={"content-type": ct})


async def tour(browser, size, vp):
    ctx = await browser.new_context(viewport=vp)
    await ctx.route("**/*", route)
    page = await ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:300]))
    page.on("console", lambda m: m.type == "error" and not NOISE.search(m.text) and errors.append("console: " + m.text[:240]))
    out = {}
    await page.goto(HOST + "/#home", wait_until="load", timeout=90000)
    await page.wait_for_timeout(9000)
    for v in VIEWS:
        before = len(errors)
        try:
            await page.evaluate(f"() => {{ location.hash = '#{v}'; }}")
            await page.wait_for_timeout(1800)
            res = await page.evaluate(CHECK)
        except Exception as e:
            res = {"chars": 0, "leaks": [], "wide": 0, "fail": str(e)[:200]}
        res["errors"] = errors[before:]
        out[v] = res
    # the split page is its own file
    try:
        sp = await ctx.new_page()
        sp_err = []
        sp.on("pageerror", lambda e: sp_err.append(str(e)[:300]))
        await sp.goto(HOST + "/split/", wait_until="load", timeout=60000)
        await sp.wait_for_timeout(2500)
        out["split"] = {"chars": len((await sp.evaluate("document.body.innerText")).strip()), "leaks": [], "wide": await sp.evaluate("document.documentElement.scrollWidth - innerWidth"), "errors": sp_err}
    except Exception as e:
        out["split"] = {"chars": 0, "leaks": [], "wide": 0, "errors": [str(e)[:200]]}
    await ctx.close()
    return out


def problems(size, res):
    out = []
    for v, r in res.items():
        if r.get("fail"):
            out.append(f"{v} ({size}): couldn't open: {r['fail']}")
        for e in r.get("errors") or []:
            out.append(f"{v} ({size}): {e}")
        if r.get("chars", 0) < 120:
            out.append(f"{v} ({size}): the page is empty ({r.get('chars', 0)} characters)")
        for l in r.get("leaks") or []:
            out.append(f"{v} ({size}): \"{l}\"")
        if size == "phone" and r.get("wide", 0) > 4:
            out.append(f"{v} ({size}): {r['wide']}px wider than the phone screen")
    return out


async def main():
    OUT.mkdir(exist_ok=True)
    found = [f"script: {x}" for x in syntax()]
    report = {"syntax": found[:]}
    if not found:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for size, vp in (("desktop", {"width": 1280, "height": 900}), ("phone", {"width": 390, "height": 844})):
                res = await tour(browser, size, vp)
                report[size] = res
                found += problems(size, res)
            await browser.close()
    # the same error on many pages is one problem
    seen, uniq = set(), []
    for x in found:
        k = re.sub(r"^[a-z]+ \((desktop|phone)\): ", "", x)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    report["problems"] = uniq
    (OUT / "report.json").write_text(json.dumps(report, indent=1))
    if uniq:
        print(f"{len(uniq)} problem(s):")
        for x in uniq[:40]:
            print(" -", x)
        (OUT / "summary.txt").write_text("\n".join(uniq[:12]))
        return 1
    print(f"All {len(VIEWS) + 1} pages fine on desktop and phone.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
