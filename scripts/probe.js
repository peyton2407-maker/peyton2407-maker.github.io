async () => {
  const out = {};
  for (const [lg, id] of [["nfl", "401873036"], ["college-football", "401871058"]]) {
    try {
      const d = await getJSON(`https://site.web.api.espn.com/apis/site/v2/sports/football/${lg}/summary?event=${id}`);
      const teams = ((d.boxscore || {}).teams || []).map((t) => ({ team: (t.team || {}).abbreviation, homeAway: t.homeAway, stats: (t.statistics || []).map((s) => [s.name, s.label, s.displayValue]) }));
      out[lg] = teams;
    } catch (e) { out[lg] = String(e); }
  }
  return out;
}
