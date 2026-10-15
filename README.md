# Double Gs

NFL and college football projections, picks, props and a public scorecard.
Live at https://peyton2407-maker.github.io/

## What's here

| Path | What it is |
| --- | --- |
| `index.html` | The Double Gs board. The whole app is this one page. |
| `split/` | The Split, college matchup sheets. |
| `data/` | Files the board loads: `snapshot.json` (games, lines, projections), `past-scorecards.json` (locked picks by week), `week-results.json` (final scores), `injuries.json`, polls, notes. |
| `hashmark.html`, `boom.html` | Old addresses. They now forward to `/` and keep the `#tab`. |
| `scripts/update_rz_touches.py` | Weekly red-zone touch counts (runs Tuesdays from `.github/workflows/rz-touches.yml`). |
| `scripts/slim_injuries.py` | Shrinks `data/injuries.json` to the fields the board reads (about 9 MB down to about 0.6 MB). |

GitHub Pages serves this branch directly (Settings → Pages → Deploy from a branch, `main`, root). There is no build step.

## When you update the data

1. Save the new `data/snapshot.json`. Finished games need `completed: true`, a final status and the real score. The board ignores a game marked finished while it still says scheduled at 0-0, so a bad pull can't grade picks or skew the team form numbers.
2. After saving a new raw ESPN injury pull to `data/injuries.json`, run `python3 scripts/slim_injuries.py`.
3. When a week ends, add its locked picks to `data/past-scorecards.json`. The home page season record is built from that file plus this week's graded plays, so it matches Scorecard and Past weeks for everyone.

## Week rules

- NFL weeks run Tuesday to Monday. The board stays on the current week until the Monday night game is final (or 4.5 hours past kickoff), then rolls.
- A quarterback on the injury report only moves a line when ESPN's depth chart has him as the starter (or he is on the season-out list in `index.html`).

Projections are for information and entertainment, not betting advice.
