#!/usr/bin/env python3
"""Copy The Split's college picks and matchup notes into the main site's data files.

The Split (split/index.html) carries this week's college slate: each game's sheet and its
desk pick. The main site reads two files built from it:
  data/desk-cfb.json    the desk pick per game (side and total), merged by game id so
                        earlier weeks stay for the scorecard
  data/split-notes.json up to four matchup notes per game, the biggest gaps between one
                        side's offense and the other side's defense
Runs in the hourly refresh, so the main site never falls behind The Split.
Usage: python3 scripts/sync_split.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "split" / "index.html"
DESK = ROOT / "data" / "desk-cfb.json"
NOTES = ROOT / "data" / "split-notes.json"


def split_data():
    s = SPLIT.read_text(encoding="utf-8")
    i = s.find("const DATA =")
    if i < 0:
        raise SystemExit("split/index.html has no DATA block")
    return json.JSONDecoder().raw_decode(s, s.find("{", i))[0]


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


# offense-vs-defense rows: (row id, label, offense wording, defense wording)
ROWS = {
    "off-pass-ypg": ("Passing", "{o} throws for {l} yards a game (#{lr}). {d} allows {r} (#{rr})."),
    "off-rush-ypg": ("Rushing", "{o} runs for {l} yards a game (#{lr}). {d} allows {r} (#{rr})."),
    "off-ypg": ("Yards", "{o} gains {l} a game (#{lr}). {d} allows {r} (#{rr})."),
    "off-ppg": ("Scoring", "{o} scores {l} a game (#{lr}). {d} allows {r} (#{rr})."),
    "sacks": ("Pass rush", "{o} gives up {l} sacks a game (#{lr}). {d} gets {r} (#{rr})."),
    "ball-security": ("Ball security", "{o} gives it away {l} times a game (#{lr}). {d} takes it away {r} (#{rr})."),
}


def notes_for(sheet):
    out = []
    away, home = sheet["away"]["abbrev"], sheet["home"]["abbrev"]
    for sec in sheet.get("sections") or []:
        if sec.get("id") == "away-off":
            off, dfn = away, home
        elif sec.get("id") == "home-off":
            off, dfn = home, away
        else:
            continue
        for row in sec.get("rows") or []:
            spec = ROWS.get(row.get("id"))
            L, R = row.get("left") or {}, row.get("right") or {}
            lr, rr = L.get("rank"), R.get("rank")
            if not spec or lr is None or rr is None or L.get("text") in (None, "") or R.get("text") in (None, ""):
                continue
            gap = abs(int(lr) - int(rr))
            if gap < 30:
                continue
            edge = f"Edge to the {dfn} defense" if int(rr) < int(lr) else f"Edge to {off}"
            line = spec[0] + ". " + spec[1].format(o=off, d=dfn, l=L["text"], r=R["text"], lr=lr, rr=rr)
            out.append((gap, {"edge": edge, "line": line}))
    out.sort(key=lambda x: -x[0])
    return [n for _, n in out[:4]]


def main():
    D = split_data()
    desk_rows = D.get("desk") or []
    sheets = D.get("sheets") or {}
    if not desk_rows and not sheets:
        print("The Split has no games; nothing to sync.")
        return 0

    try:
        old = json.loads(DESK.read_text()) if DESK.exists() else []
    except Exception:
        old = []
    by_id = {str(r["id"]): r for r in old if r and r.get("id") is not None}
    for r in desk_rows:
        if r and r.get("id") is not None:
            by_id[str(r["id"])] = r
    merged = sorted(by_id.values(), key=lambda r: (str(r.get("date") or ""), str(r["id"])))
    DESK.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")) + "\n")

    try:
        notes = json.loads(NOTES.read_text()) if NOTES.exists() else {}
    except Exception:
        notes = {}
    made = 0
    for gid, sh in sheets.items():
        n = notes_for(sh)
        if n:
            notes[str(gid)] = {"away": sh["away"]["abbrev"], "home": sh["home"]["abbrev"], "notes": n}
            made += 1
    NOTES.write_text(json.dumps(notes, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Split week {D.get('slate', {}).get('week')}: {len(desk_rows)} desk picks, {made} games with matchup notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
