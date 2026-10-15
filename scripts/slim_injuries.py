#!/usr/bin/env python3
"""Shrink data/injuries.json to the fields the board reads.

The raw ESPN injury feed is about 9 MB, mostly link boilerplate for every player.
The board only needs the name, id, position, status, dates, comments and injury
details, so this keeps those and drops the rest (about 95% smaller).

Run it after saving a new injury pull:
    python3 scripts/slim_injuries.py            # rewrites data/injuries.json
    python3 scripts/slim_injuries.py --check    # only prints the sizes
"""
import json
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "injuries.json"


def athlete_id(a):
    if a.get("id"):
        return str(a["id"])
    href = (a.get("headshot") or {}).get("href") or ""
    m = re.search(r"(\d+)\.png", href) or re.search(r"/id/(\d+)", json.dumps(a.get("links") or []))
    return m.group(1) if m else ""


def slim_row(x):
    a = x.get("athlete") or {}
    det = x.get("details") or {}
    typ = x.get("type")
    row = {
        "id": x.get("id", ""),
        "status": x.get("status", ""),
        "date": x.get("date", ""),
        "shortComment": x.get("shortComment") or x.get("short") or "",
        "longComment": x.get("longComment") or x.get("long") or "",
        "athlete": {
            "id": athlete_id(a),
            "displayName": a.get("displayName") or x.get("name") or "",
            "shortName": a.get("shortName", ""),
            "position": {"abbreviation": ((a.get("position") or {}).get("abbreviation")) or x.get("pos") or ""},
        },
    }
    keep = {k: det[k] for k in ("type", "side", "location", "returnDate") if det.get(k)}
    fant = (det.get("fantasyStatus") or {}).get("description")
    if fant:
        keep["fantasyStatus"] = {"description": fant}
    if keep:
        row["details"] = keep
    if isinstance(typ, dict):
        t = {k: typ[k] for k in ("description", "name") if typ.get(k)}
        if t:
            row["type"] = t
    elif typ:
        row["type"] = typ
    return row


def slim_feed(feed):
    if not isinstance(feed, dict):
        return feed
    out = {k: v for k, v in feed.items() if k != "injuries"}
    out["injuries"] = [
        {"id": t.get("id"), "displayName": t.get("displayName", ""), "injuries": [slim_row(x) for x in (t.get("injuries") or [])]}
        for t in (feed.get("injuries") or [])
    ]
    return out


def main():
    raw = PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    slim = {k: (slim_feed(v) if k in ("nfl", "cfb") else v) for k, v in data.items()}
    text = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    print(f"{PATH.name}: {len(raw.encode()):,} bytes -> {len(text.encode()):,} bytes")
    if "--check" not in sys.argv:
        PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
