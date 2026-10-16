#!/usr/bin/env python3
"""Check the board's chances against what actually happened, and save the correction.

For every game this season the site posted before kickoff, take the last version of the
board committed before that game kicked off (data/snapshot.json, or the board embedded in
index.html for older commits). Work out the chance that board gave each side, the same way
the parlay builder does (projected margin and total, spread of outcomes from LIVE in
index.html, NFL margins weighted by how often games really land on each number), and
compare with the final score in data/week-results.json.

Then fit one number per league and market: how much of the board's lean to keep.
    checked chance = market chance + keep * (board chance - market chance)
keep = 1 means the board's chances held up; keep = 0 means the market's own price did just
as well. Writes data/calibration.json, which the parlay builder reads.

Needs the full git history (actions/checkout with fetch-depth: 0).
Usage: python3 scripts/calibrate.py [--repo .] [--out data/calibration.json]
"""
import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NFL_SIGMA, CFB_SIGMA, CFB_TOTAL_SIGMA, NFL_TOTAL_SIGMA = 13.0, 15.25, 15.9, 13.2
# College margins: same idea as KEYW, fit to 2021-2023 college games around the closing
# spread (15.25-point spread of outcomes; no ties). Same table as PB_CFB_KEY in index.html.
CFB_KEYW = [0.0004, 0.774, 0.8938, 2.674, 0.8834, 0.5773, 0.9259, 2.271, 0.7904, 0.3827, 1.2699, 0.5914, 0.4441, 0.6318, 1.4908, 0.578, 0.3662, 1.3878, 0.7773, 0.4635, 0.7638, 1.5479, 0.4416, 0.7585, 1.3767]
# How much more (or less) often an NFL game ends on each final margin than a plain bell
# curve says. Fit to every NFL game 2015-2024 (nflverse games.csv, 3,108 games) around the
# closing spread with an outcome spread of 13 points; index = margin in points, margins past
# 24 use 1. Fit on 2015-2021 alone, it predicted 2022-2024 teaser legs (favorites of 7.5-8.5
# and underdogs of 1.5-2.5 moved 6 points) at 71.6 percent against 73.0 actual; a plain bell
# curve said 67.6. The builder uses the same table (PB_NFL_KEY in index.html).
KEYW = [0.1376, 0.8652, 0.903, 2.9525, 0.9423, 0.9163, 1.4725, 1.9058, 0.9768, 0.3872, 1.168, 0.5431, 0.5297, 0.5905, 1.5898, 0.5359, 0.8312, 1.362, 0.9512, 0.5198, 1.0436, 1.2415, 0.6583, 0.9334, 1.5674]


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def npdf(x, mu, sd):
    return math.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * math.sqrt(2 * math.pi))


def nfl_margin_pmf(mu, sd, table=None):
    table = table or KEYW
    pmf = {}
    for m in range(-70, 71):
        w = table[abs(m)] if abs(m) < len(table) else 1.0
        pmf[m] = npdf(m, mu, sd) * w
    s = sum(pmf.values())
    return {m: v / s for m, v in pmf.items()}


_CENTER = {}


def nfl_center(x, sd=NFL_SIGMA, table=None):
    """A posted NFL line splits outcomes about 50/50; games bunch on 3 and 7, so find the
    center that puts as much weight above x as below it (same as pbNflCenter in index.html)."""
    key = (round(x, 2), sd, "c" if table is CFB_KEYW else "n")
    if key in _CENTER:
        return _CENTER[key]
    lo, hi = x - 8, x + 8
    for _ in range(32):
        mid = (lo + hi) / 2
        d = nfl_margin_pmf(mid, sd, table)
        above = sum(p for m, p in d.items() if m > x)
        below = sum(p for m, p in d.items() if m < x)
        if above < below:
            lo = mid
        else:
            hi = mid
    _CENTER[key] = (lo + hi) / 2
    return _CENTER[key]


def side_chance(league, mu, line_home):
    """Chance the home side covers line_home (home spread), and push chance.
    mu is the projected home margin (the board's line, as a margin)."""
    if league == "nfl":
        pmf = nfl_margin_pmf(nfl_center(mu), NFL_SIGMA)
        win = sum(p for m, p in pmf.items() if m + line_home > 0)
        push = sum(p for m, p in pmf.items() if m + line_home == 0)
        return win, push
    pmf = nfl_margin_pmf(nfl_center(mu, CFB_SIGMA, CFB_KEYW), CFB_SIGMA, CFB_KEYW)
    win = sum(p for m, p in pmf.items() if m + line_home > 0)
    push = sum(p for m, p in pmf.items() if m + line_home == 0)
    return win, push


def total_chance(league, mu, line):
    sd = NFL_TOTAL_SIGMA if league == "nfl" else CFB_TOTAL_SIGMA
    whole = abs(line - round(line)) < 1e-9
    if whole:
        hi = ncdf((line + 0.5 - mu) / sd)
        lo = ncdf((line - 0.5 - mu) / sd)
        return 1 - hi, hi - lo
    return 1 - ncdf((line - mu) / sd), 0.0


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True).stdout


def ts(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def american_prob(v):
    try:
        a = float(str(v).replace("+", ""))
    except Exception:
        return None
    if abs(a) < 100:
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def boards(repo):
    """Yield (commit_time, board) for every commit, oldest first; identical blobs parsed once."""
    dec = json.JSONDecoder()
    cache = {}
    commits = [l.split() for l in git(repo, "log", "--reverse", "--format=%H %ct", "HEAD").decode().split("\n") if l.strip()]
    for sha, ct in commits:
        out = []
        for path in ("data/snapshot.json", "index.html"):
            h = git(repo, "rev-parse", f"{sha}:{path}").decode().strip()
            if not h or h.startswith(sha):
                continue
            if h not in cache:
                raw = git(repo, "cat-file", "-p", h)
                obj = None
                try:
                    if path.endswith(".json"):
                        obj = json.loads(raw)
                    else:
                        s = raw.decode("utf-8", "replace")
                        i = s.find("window.HASHMARK = ")
                        if i >= 0:
                            obj = dec.raw_decode(s, i + len("window.HASHMARK = "))[0]
                except Exception:
                    obj = None
                cache[h] = obj
            if cache[h]:
                out.append(cache[h])
        yield int(ct), out


def collect(repo):
    last = {}
    for ct, objs in boards(repo):
        for d in objs:
            for g in d.get("games") or []:
                kick = ts(g.get("date"))
                if kick is None or ct >= kick or g.get("completed"):
                    continue
                p, o = g.get("proj") or {}, g.get("odds") or {}
                if p.get("hashmark_home_spread") is None or o.get("home_spread") is None:
                    continue
                last[str(g["id"])] = {
                    "league": g.get("league"), "ct": ct,
                    "our_home": float(p["hashmark_home_spread"]),
                    "our_total": p.get("hashmark_total"),
                    "home_spread": float(o["home_spread"]), "total": o.get("total"),
                    "home_ml": o.get("home_ml"), "away_ml": o.get("away_ml"),
                }
    return last


def fit_keep(rows):
    """Max-likelihood keep in [0, 1.2] for checked = market + keep * (board - market)."""
    if len(rows) < 20:
        return None, None
    best = None
    for i in range(0, 121):
        k = i / 100
        ll = 0.0
        for board, market, hit in rows:
            q = min(0.995, max(0.005, market + k * (board - market)))
            ll += math.log(q if hit else 1 - q)
        if best is None or ll > best[1]:
            best = (k, ll)
    # rough standard error from the curvature of the log-likelihood around the best keep
    k0 = best[0]
    def ll_at(k):
        t = 0.0
        for board, market, hit in rows:
            q = min(0.995, max(0.005, market + k * (board - market)))
            t += math.log(q if hit else 1 - q)
        return t
    h = 0.05
    curv = (ll_at(k0 + h) - 2 * ll_at(k0) + ll_at(max(0.0, k0 - h))) / (h * h)
    se = math.sqrt(-1 / curv) if curv < 0 else None
    return k0, se


def buckets(rows):
    edges = [(0.5, 0.55), (0.55, 0.6), (0.6, 0.65), (0.65, 0.7), (0.7, 1.01)]
    out = []
    for lo, hi in edges:
        sel = [(b, h) for b, m, h in rows if lo <= b < hi]
        if sel:
            out.append({"from": lo, "to": min(hi, 1.0), "n": len(sel),
                        "board": round(sum(b for b, _ in sel) / len(sel), 3),
                        "actual": round(sum(1 for _, h in sel if h) / len(sel), 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--out", default=str(ROOT / "data" / "calibration.json"))
    args = ap.parse_args()
    repo = Path(args.repo)
    finals = {str(r["id"]): r for r in json.loads((repo / "data" / "week-results.json").read_text())
              if r and r.get("hs") is not None and r.get("as") is not None}
    games = collect(repo)
    data = {lg: {"spread": [], "total": [], "ml": []} for lg in ("nfl", "cfb")}
    for gid, g in games.items():
        f = finals.get(gid)
        lg = g["league"]
        if not f or lg not in data:
            continue
        margin = float(f["hs"]) - float(f["as"])
        total_pts = float(f["hs"]) + float(f["as"])
        mu = -g["our_home"]
        # spread: score the side the board leaned to (the chance above 50%)
        win, push = side_chance(lg, mu, g["home_spread"])
        res = margin + g["home_spread"]
        if res != 0 and (1 - push) > 0:
            ph = win / (1 - push)               # chance home covers, pushes set aside
            lean_home = ph >= 0.5
            board = ph if lean_home else 1 - ph
            hit = (res > 0) == lean_home
            data[lg]["spread"].append((board, 0.5, hit))
        if g["our_total"] is not None and g["total"] is not None:
            tw, tp = total_chance(lg, float(g["our_total"]), float(g["total"]))
            tres = total_pts - float(g["total"])
            if tres != 0 and (1 - tp) > 0:
                po = tw / (1 - tp)
                lean_over = po >= 0.5
                board = po if lean_over else 1 - po
                data[lg]["total"].append((board, 0.5, (tres > 0) == lean_over))
        ih, ia = american_prob(g["home_ml"]), american_prob(g["away_ml"])
        if ih and ia and margin != 0:
            mh = ih / (ih + ia)
            if lg == "nfl":
                pmf = nfl_margin_pmf(nfl_center(mu), NFL_SIGMA)
                bh = sum(p for m, p in pmf.items() if m > 0) / max(1e-9, 1 - pmf.get(0, 0))
            else:
                pmf = nfl_margin_pmf(nfl_center(mu, CFB_SIGMA, CFB_KEYW), CFB_SIGMA, CFB_KEYW)
                bh = sum(p for m, p in pmf.items() if m > 0) / max(1e-9, 1 - pmf.get(0, 0))
            # score the side the board liked more than the market did
            if bh >= mh:
                data[lg]["ml"].append((bh, mh, margin > 0))
            else:
                data[lg]["ml"].append((1 - bh, 1 - mh, margin < 0))
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "method": (
        "Every game since Sept 21: the last board posted before kickoff, the chance it gave each side, "
        "and the final score. keep = how much of the board's lean over the market's price held up."), "leagues": {}}
    for lg, mk in data.items():
        out["leagues"][lg] = {}
        for name, rows in mk.items():
            keep, se = fit_keep(rows)
            hits = sum(1 for _, _, h in rows if h)
            out["leagues"][lg][name] = {
                "n": len(rows), "lean_hits": hits, "lean_rate": round(hits / len(rows), 3) if rows else None,
                "keep": keep, "keep_se": round(se, 2) if se else None,
                "buckets": buckets(rows) if name != "ml" else [],
            }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    for lg, mk in out["leagues"].items():
        for name, r in mk.items():
            print(lg, name, "n", r["n"], "lean hit", r["lean_rate"], "keep", r["keep"], "+/-", r["keep_se"])


if __name__ == "__main__":
    main()
