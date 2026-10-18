async () => {
  // what ESPN's fantasy feed returns per player: which weeks have projections
  const url = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3?view=kona_player_info&scoringPeriodId=1";
  const filt = JSON.stringify({ players: { limit: 5, sortPercOwned: { sortPriority: 1, sortAsc: false } } });
  const out = {};
  for (const sp of [1, 6, 7]) {
    const u = url.replace("scoringPeriodId=1", "scoringPeriodId=" + sp);
    try {
      const d = await getJSON(u, { Accept: "application/json", "X-Fantasy-Filter": filt });
      out["sp" + sp] = (d.players || []).slice(0, 2).map((r) => ({ name: r.player.fullName, stats: (r.player.stats || []).map((s) => [s.seasonId, s.scoringPeriodId, s.statSourceId, s.statSplitTypeId, Math.round((s.stats || {})["3"] || 0), Math.round((s.stats || {})["24"] || 0), Math.round((s.stats || {})["42"] || 0)]) }));
    } catch (e) { out["sp" + sp] = String(e); }
  }
  out.week = currentNflWeekNumber();
  return out;
}
