async () => {
  await new Promise((r) => setTimeout(r, 5000));
  const out = [];
  (DATA.games || []).filter((g) => g.league === "nfl" && !g.completed && isThisNflWeek(g)).forEach((g) => {
    const s = g.situational || {};
    out.push({ game: g.short_name, margin_adj: s.margin_adj, total_adj: s.total_adj, notes: s.notes, line: (g.odds || {}).details, total: (g.odds || {}).total, ours: (g.proj || {}).hashmark_home_spread, ourTot: (g.proj || {}).hashmark_total, pick: (g.proj || {}).pick });
  });
  return out;
}
