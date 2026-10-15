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
| `data/locks.json` | Picks, plays of the day and this week's card, locked 90 minutes before kickoff. Same for every visitor. |
| `scripts/lock_runner.py` | Runs every 15 minutes from `.github/workflows/lock-picks.yml`: opens the live board, locks what's due, grades finished plays of the day, and moves finished weeks into `past-scorecards.json`. |
| `scripts/slim_injuries.py` | Shrinks `data/injuries.json` to the fields the board reads (about 9 MB down to about 0.6 MB). |

GitHub Pages serves this branch directly (Settings → Pages → Deploy from a branch, `main`, root). There is no build step.

## When you update the data

1. Save the new `data/snapshot.json`. Finished games need `completed: true`, a final status and the real score. The board ignores a game marked finished while it still says scheduled at 0-0, so a bad pull can't grade picks or skew the team form numbers.
2. After saving a new raw ESPN injury pull to `data/injuries.json`, run `python3 scripts/slim_injuries.py`.
3. Finished weeks are added to `data/past-scorecards.json` automatically by the Lock picks job (below). You can still add or fix a week by hand; the job never overwrites a week that's already there. The home page season record is built from that file plus this week's graded plays, so it matches Scorecard and Past weeks for everyone.

## Locked picks

The "Lock picks" GitHub job locks each game's scorecard pick 90 minutes before kickoff, the play of the day the same way, and this week's card at Thursday noon ET (or 90 minutes before its first game). Once every locked game of a week has a final, that week is added to `past-scorecards.json` (a week already there is never overwritten). Run it by hand from the Actions tab with "Run workflow". Test it locally with `python3 scripts/lock_runner.py --local . --now 2026-10-15T23:00:00Z --dry-run`.

## Week rules

- NFL weeks run Tuesday to Monday. The board stays on the current week until the Monday night game is final (or 4.5 hours past kickoff), then rolls.
- A quarterback on the injury report only moves a line when ESPN's depth chart has him as the starter (or he is on the season-out list in `index.html`).

Projections are for information and entertainment, not betting advice.
