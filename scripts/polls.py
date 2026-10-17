#!/usr/bin/env python3
"""Save ESPN's current AP and Coaches college polls to data/cfb-polls.json.

The site reads this when the browser can't reach ESPN itself. The polls are stored in
ESPN's own shape (parseCfbPoll in index.html reads it). If the feed fails or comes back
without an AP poll, the old file stays.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "cfb-polls.json"
URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"


TEAM_KEYS = ("id", "uid", "displayName", "location", "name", "nickname", "abbreviation", "shortDisplayName", "color")
RANK_KEYS = ("current", "previous", "points", "firstPlaceVotes", "trend", "recordSummary", "date")


def slim(poll):
    """Only what the site reads (parseCfbPoll): about a tenth of ESPN's full answer."""
    if not poll:
        return poll

    def row(x):
        t = x.get("team") or {}
        team = {k: t[k] for k in TEAM_KEYS if k in t}
        logo = next((L.get("href") for L in t.get("logos") or [] if "default" in (L.get("rel") or [])), None) or next((L.get("href") for L in t.get("logos") or []), None)
        if logo:
            team["logos"] = [{"href": logo, "rel": ["full", "default"]}]
        grp = t.get("groups") or {}
        if grp.get("shortName"):
            team["groups"] = {"shortName": grp["shortName"]}
        out = {k: x[k] for k in RANK_KEYS if k in x}
        out["team"] = team
        return out

    keep = {k: poll[k] for k in ("name", "shortName", "type", "headline", "shortHeadline", "lastUpdated", "date") if k in poll}
    if poll.get("occurrence"):
        keep["occurrence"] = {"displayValue": poll["occurrence"].get("displayValue"), "number": poll["occurrence"].get("number")}
    for k in ("ranks", "others", "droppedOut"):
        keep[k] = [row(x) for x in poll.get(k) or []]
    return keep


def main():
    try:
        req = urllib.request.Request(URL, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Double Gs polls)"})
        with urllib.request.urlopen(req, timeout=30) as res:
            d = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print("polls feed error:", e)
        return 0
    out = {"pulled": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ap": None, "coaches": None}
    for p in d.get("rankings") or []:
        if p.get("type") == "ap":
            out["ap"] = p
        elif p.get("type") == "usa":
            out["coaches"] = p
    out["ap"], out["coaches"] = slim(out["ap"]), slim(out["coaches"])
    if not out["ap"] or len(out["ap"].get("ranks") or []) < 25:
        print("no full AP poll in the feed; keeping the old file")
        return 0
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print("saved", out["ap"].get("headline") or "AP poll", "and", (out["coaches"] or {}).get("headline") or "no coaches poll")
    return 0


if __name__ == "__main__":
    sys.exit(main())
