async () => {
  try { await ensurePotdProps(); } catch (e) {}
  const rows = nextPropRows().filter((p) => String(p.game_id) === "401873023");
  const leans = rows.map((p) => { const x = postedLean(p); return x && [p.name, x.take, x.line, x.m.key, x.price, x.book, Math.round(x.fair * 1000) / 10, Math.round(x.chance * 1000) / 10, Math.round((x.value || 0) * 1000) / 10]; }).filter(Boolean).sort((a, b) => b[8] - a[8]);
  window.__potdRepick = true; let f = null; try { f = potdPick("nfl"); } finally { window.__potdRepick = false; }
  const shown = potdPick("nfl");
  const sun = nextPropRows().filter((p) => String(p.game_id) !== "401873023").length;
  return { players: rows.length, leans, freshPotd: f && [f.g.short_name, f.line, f.price, f.book, f.why], shownPotd: shown && [shown.line, shown.provisional, shown.locked], otherGamesPlayers: sun };
}
