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
| `data/locks.json` | Picks, plays of the day and this week's card, locked 90 minutes before kickoff. Same for every visitor. |
| `scripts/lock_runner.py` | Runs every 15 minutes from `.github/workflows/lock-picks.yml`: opens the live board, locks what's due, grades finished plays of the day, and moves finished weeks into `past-scorecards.json`. |
| `scripts/refresh_data.py` | Runs every hour from `.github/workflows/refresh-data.yml`: updates scores, lines, new games, team ratings and finals in `snapshot.json` and `week-results.json` from ESPN, using the board's own parsers. Picks are never edited here. |
| `scripts/props.py` | Runs inside the hourly Refresh data job after `books.py`: saves real player-prop prices (DraftKings, FanDuel, BetMGM, BetRivers) to `data/props.json`. With the `ODDS_API_KEY` repository secret it uses The Odds API (free plan: each game once, about a day before kickoff, ~325 of the 500 monthly credits; set the repository variable `ODDS_API_PLAN` to `paid` on a paid plan for hourly updates). Without a key it tries Action Network's feed, which has returned no props to GitHub's servers so far. `data/props-status.json` says what happened on the last run, including credits left. |
| `scripts/books.py` | Runs inside the hourly Refresh data job: saves every big US sportsbook's spread, total and moneyline for this week's games to `data/books.json` (from Action Network's public feed), so the parlay builder can show the best number for each leg. If the feed is down the old file stays. |
| `scripts/calibrate.py` | Runs every Tuesday from `.github/workflows/calibrate.yml`: takes the board posted before every kickoff this season, works out the chance it gave each side, compares with the final scores, and saves how much of the board's lean held up to `data/calibration.json`. The parlay builder blends the book's line with that much of our lean. |
| `scripts/slim_injuries.py` | Shrinks `data/injuries.json` to the fields the board reads (about 9 MB down to about 0.6 MB). |

GitHub Pages serves this branch directly (Settings → Pages → Deploy from a branch, `main`, root). There is no build step.

## When you update the data

1. The Refresh data job keeps `data/snapshot.json` current on its own. If you save a new one by hand, finished games need `completed: true`, a final status and the real score. The board ignores a game marked finished while it still says scheduled at 0-0, so a bad pull can't grade picks or skew the team form numbers.
2. After saving a new raw ESPN injury pull to `data/injuries.json`, run `python3 scripts/slim_injuries.py`.
3. Finished weeks are added to `data/past-scorecards.json` automatically by the Lock picks job (below). You can still add or fix a week by hand; the job never overwrites a week that's already there. The home page season record is built from that file plus this week's graded plays, so it matches Scorecard and Past weeks for everyone.

## Locked picks

The "Lock picks" GitHub job locks each game's scorecard pick 90 minutes before kickoff, the play of the day the same way, and this week's card at Thursday noon ET (or 90 minutes before its first game). Each run within 20 minutes of kickoff also saves the closing line, so every locked pick shows how many points it beat (or lost to) the close. Once every locked game of a week has a final, that week is added to `past-scorecards.json` (a week already there is never overwritten). Run it by hand from the Actions tab with "Run workflow". Test it locally with `python3 scripts/lock_runner.py --local . --now 2026-10-15T23:00:00Z --dry-run`.

## Parlay builder

Boom Room → Parlay builder (`#builder`). Tap spreads, totals, moneylines and NFL player props, then play them as a parlay, a teaser or a round robin.

- Every chance is "checked": it starts from the book's own line and keeps only as much of our board's lean as `data/calibration.json` says held up this season (small samples keep half).
- NFL margins are weighted by how often real games end on each number (3, 7, 10, 14...). The weights were fit to every NFL game from 2015 to 2024 and are in `index.html` (`PB_NFL_KEY`) and `scripts/calibrate.py`. Fit on 2015-2021, they predicted 2022-2024 teaser legs at 71.6% against 73.0% actual.
- Legs from one game are priced together. Teasers and round robins take one leg per game.
- College margins are weighted the same way (3 and 7 decide about 10% and 8% of college games) and land a typical 15.25 points from the line at every spread size; college totals land 15.9 points from the closing total. Fit to 2021-2023 college games (cfbfastR-data lines and scores) and checked on 2024-2025: better than the old formula at predicting final margins, who wins, teaser legs and totals.
- Confidence labels on the board use the checked lean too, so college picks show about 50% until the board's college leans start beating the book.
- The − and + buttons sell or buy half points at an estimated alternate-line price. Any price can be typed in.
- Bet size uses the Kelly method on the bankroll you enter, with a profit boost if you have one.
- Player props use real prices when we have them: `scripts/props.py` (hourly) saves every big book's prop prices to `data/props.json`, and the builder also tries DraftKings' prices from the visitor's browser (the player pages' source). Without either, a prop shows a typical -115 and says so. `data/props-status.json` records what the feed returned on the last run.
- Live sweat: once a leg's game kicks off, the ticket turns into a tracker (won, lost, push, or the live chance from the board's in-game projection, refreshed every minute). Each leg keeps the line and price it had before kickoff. With one leg left on a parlay, it works out the hedge: the bet on the other side that locks in a profit, the one that just gets your stake back, and what certainty costs on average.
- The ticket is saved in the visitor's browser, and "Copy link" opens the same ticket anywhere.

## Week rules

- NFL weeks run Tuesday to Monday. The board stays on the current week until the Monday night game is final (or 4.5 hours past kickoff), then rolls.
- A quarterback on the injury report only moves a line when ESPN's depth chart has him as the starter (or he is on the season-out list in `index.html`).

Projections are for information and entertainment, not betting advice.

## The Split, built automatically

`scripts/build_split.py` rebuilds The Split (`split/index.html`) for the current college week
from ESPN every 6 hours (`.github/workflows/build-split.yml`), and moves to the new week on
Monday mornings by itself:

- **Games:** each week's FBS games, DraftKings lines and prices, records, rankings, TV,
  venue and each team's leading passer, rusher and receiver.
- **Sheets:** power and résumé from ESPN's power index, then about 40 season stats for
  every FBS team (own and allowed, from one league-wide request), each ranked across FBS.
- **Play grades:** `split/advanced.json` is rebuilt once a day by running The Split's own
  play-by-play grading on the server, which also refreshes against-the-spread records.
  Coaches and roster talent carry over.
- **Projections and picks:** the projected margin starts at the market's line and moves 35% of
  the way toward a blend of the stats matchup and the FPI gap; the projected total is the
  market's. A side is picked only when both are 3+ points off the line in the same
  direction. No totals are picked: in a 2021-2025 backtest (`scripts/backtest_split.py`) a
  stats total far off the line lost 44% of the time, and side picks were about 50-51%.
  A game within two hours of kickoff keeps its pick.

`scripts/sync_split.py` then copies the picks, leading passers and matchup notes to the
main site.
