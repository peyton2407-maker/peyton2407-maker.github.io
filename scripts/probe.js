async () => {
  await new Promise((r) => setTimeout(r, 5000));
  return (DATA.games || []).filter((g) => g.league === "nfl" && !g.completed && isThisNflWeek(g)).map((g) => { const s = g.situational || {}; return { game: g.short_name, line: (g.odds || {}).details, ours: (g.proj || {}).hashmark_home_spread, adj: s.margin_adj, pick: (g.proj || {}).pick, notes: s.notes }; });
}
