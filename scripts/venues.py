#!/usr/bin/env python3
"""Map coordinates for every stadium town on the board, so every outdoor game gets a forecast.

The page knows about a hundred cities by heart; college games are played in many more
(Laramie, Boone, Kennesaw...). For each game in data/snapshot.json whose city isn't saved
yet, this asks Open-Meteo's free geocoder (no key) for the town, keeps the match in the right
state (or country), and saves it to data/venues.json: {"City|ST": [lat, lon]}. Only missing
towns are looked up, so most runs make no requests.
Usage: python3 scripts/venues.py
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "venues.json"
GEO = "https://geocoding-api.open-meteo.com/v1/search?"
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
COUNTRY = {"USA": "US", "United States": "US", "England": "GB", "United Kingdom": "GB", "Ireland": "IE",
           "Germany": "DE", "Mexico": "MX", "Brazil": "BR", "Spain": "ES", "France": "FR", "Australia": "AU", "Canada": "CA"}


def key(city, state, country):
    return f"{city}|{state or country or ''}"


def lookup(city, state, country):
    cc = COUNTRY.get(country or "USA", "")
    q = {"name": city, "count": 10, "language": "en", "format": "json"}
    if cc:
        q["countryCode"] = cc
    req = urllib.request.Request(GEO + urllib.parse.urlencode(q), headers={"User-Agent": "Mozilla/5.0 (Double Gs venues)"})
    with urllib.request.urlopen(req, timeout=20) as res:
        rows = json.loads(res.read().decode("utf-8")).get("results") or []
    want = STATES.get(state or "")
    for r in rows:
        if want and r.get("admin1") != want:
            continue
        return [round(float(r["latitude"]), 3), round(float(r["longitude"]), 3)]
    if not want and rows:
        return [round(float(rows[0]["latitude"]), 3), round(float(rows[0]["longitude"]), 3)]
    return None


def main():
    try:
        have = json.loads(OUT.read_text()) if OUT.exists() else {}
    except Exception:
        have = {}
    snap = json.loads(SNAP.read_text())
    todo = {}
    for g in snap.get("games") or []:
        city = str(g.get("city") or "").strip()
        if not city or g.get("indoor"):
            continue
        k = key(city, g.get("state"), g.get("country"))
        if k not in have:
            todo[k] = (city, g.get("state"), g.get("country"))
    found = 0
    for k, (city, state, country) in sorted(todo.items()):
        try:
            xy = lookup(city, state, country)
        except Exception as e:
            print("geocoder error", k, e)
            continue
        if xy:
            have[k] = xy
            found += 1
        else:
            print("no match for", k)
        time.sleep(0.15)
    if found:
        OUT.write_text(json.dumps(have, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"{len(todo)} towns to look up; found {found}; {len(have)} saved")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("venues error:", e)
        sys.exit(0)
