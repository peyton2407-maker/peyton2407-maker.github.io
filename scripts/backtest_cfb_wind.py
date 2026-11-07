#!/usr/bin/env python3
"""Wind and rain at kickoff vs the closing total, FBS vs FBS college games 2021-2025, split 2021-23 | 2024-25.
Runs on GitHub (.github/workflows/backtest-wind.yml). No Odds API calls: lines are data/backtests/cfb-hist-lines.csv
(CollegeFootballData closing consensus), stadiums from ESPN's team pages, weather from Open-Meteo's free archive.
Neutral-site games and domes are left out (the stadium isn't the home team's, or the weather doesn't reach the field)."""
import csv, json, time, urllib.request, urllib.parse, collections, sys
from datetime import datetime, timedelta, timezone

def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Double Gs backtest)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1: print("fail", url[:120], e); return None
            time.sleep(3 * (i + 1))

G = [r for r in csv.DictReader(open("data/backtests/cfb-hist-lines.csv")) if r["neutral_site"] != "True"]
print("games (not neutral):", len(G))
# stadium of each home team: ESPN team page -> venue city/state + indoor; then Open-Meteo geocoding
venue = {}
for tid in sorted({r["home_id"] for r in G}):
    j = get(f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{tid}")
    t = (j or {}).get("team") or {}
    v = t.get("venue") or (t.get("franchise") or {}).get("venue") or {}
    if not (v.get("address") or {}).get("city"):
        # the core API: the team's venue is a link
        c = get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/2025/teams/{tid}?lang=en&region=us")
        ref = ((c or {}).get("venue") or {}).get("$ref")
        if ref: v = get(ref.replace("http://", "https://")) or v
    if not venue and not (v.get("address") or {}).get("city"):
        print("debug team keys", tid, list(t)[:30], json.dumps(v)[:300])
    a = v.get("address") or {}
    city, state = a.get("city"), a.get("state")
    if not city: continue
    q = get("https://geocoding-api.open-meteo.com/v1/search?count=10&language=en&format=json&countryCode=US&name=" + urllib.parse.quote(city))
    res = (q or {}).get("results") or []
    pick = next((x for x in res if state and (x.get("admin1", "").lower().startswith(state.lower()) or state.lower() in (x.get("admin1_code") or "").lower())), None) or (res[0] if res else None)
    if not pick: continue
    venue[tid] = dict(lat=pick["latitude"], lon=pick["longitude"], indoor=bool(v.get("indoor")), name=v.get("fullName"), city=city, state=state)
    time.sleep(0.15)
print("stadiums found:", len(venue), "indoor:", sum(v["indoor"] for v in venue.values()))
# weather: one archive pull per stadium for the whole span, hourly wind (mph) and precipitation (in)
wx = {}
for tid, v in venue.items():
    if v["indoor"]: continue
    j = get(f"https://archive-api.open-meteo.com/v1/archive?latitude={v['lat']}&longitude={v['lon']}&start_date=2021-08-20&end_date=2026-01-20&hourly=precipitation,wind_speed_10m,wind_gusts_10m&wind_speed_unit=mph&precipitation_unit=inch&timezone=GMT")
    if not j: continue
    h = j["hourly"]; wx[tid] = {t: (w, g, p) for t, w, g, p in zip(h["time"], h["wind_speed_10m"], h["wind_gusts_10m"], h["precipitation"])}
    time.sleep(0.4)
print("stadiums with weather:", len(wx))
R = []
for r in G:
    W = wx.get(r["home_id"])
    if not W: continue
    k = datetime.fromisoformat(r["start_date"].replace("Z", "+00:00")).replace(minute=0, second=0, microsecond=0)
    hrs = [W.get((k + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00")) for i in range(4)]
    hrs = [x for x in hrs if x and x[0] is not None]
    if not hrs: continue
    wind = sum(x[0] for x in hrs) / len(hrs); gust = max((x[1] or 0) for x in hrs); rain = sum((x[2] or 0) for x in hrs)
    tl = float(r["total_line"]); tot = float(r["home_points"]) + float(r["away_points"])
    R.append(dict(s=int(r["season"]), tl=tl, tot=tot, wind=wind, gust=gust, rain=rain, conf=r["conference_game"] == "True"))
print("games graded:", len(R))
def show(name, f):
    out = []
    for ss in ((2021, 2022, 2023), (2024, 2025)):
        res = [(x["tot"] < x["tl"]) for x in R if x["s"] in ss and f(x) and x["tot"] != x["tl"]]
        diff = [x["tot"] - x["tl"] for x in R if x["s"] in ss and f(x)]
        w = sum(res); out.append((w, len(res) - w, 100 * w / len(res) if res else 0, sum(diff) / len(diff) if diff else 0))
    a, b = out; n = a[0] + a[1] + b[0] + b[1]
    ok = a[2] >= 53 and b[2] >= 53 and a[0] + a[1] >= 40 and b[0] + b[1] >= 30
    print(f"{name:46s} unders {a[0]:4d}-{a[1]:<4d} {a[2]:5.1f}% (avg {a[3]:+5.1f}) | {b[0]:4d}-{b[1]:<4d} {b[2]:5.1f}% (avg {b[3]:+5.1f}) | n={n}{'  <== holds' if ok else ''}")
dry = lambda x: x["rain"] < 0.05
show("all outdoor games", lambda x: True)
for c in (8, 10, 12, 15, 18, 20):
    show(f"wind {c}+ mph, dry", lambda x, c=c: x["wind"] >= c and dry(x))
for c in (25, 30, 35):
    show(f"gusts {c}+ mph, dry", lambda x, c=c: x["gust"] >= c and dry(x))
show("wind 12+ mph, any rain", lambda x: x["wind"] >= 12)
show("wind 15+ mph, any rain", lambda x: x["wind"] >= 15)
show("rain 0.1+ in over the game", lambda x: x["rain"] >= 0.1)
show("rain 0.25+ in over the game", lambda x: x["rain"] >= 0.25)
show("wind 12+ and total under 58", lambda x: x["wind"] >= 12 and dry(x) and x["tl"] < 58)
show("wind 12+ and total 58+", lambda x: x["wind"] >= 12 and dry(x) and x["tl"] >= 58)
show("wind 15+ and total under 58", lambda x: x["wind"] >= 15 and dry(x) and x["tl"] < 58)
show("calm (under 5 mph), dry: overs?", lambda x: x["wind"] < 5 and dry(x))
