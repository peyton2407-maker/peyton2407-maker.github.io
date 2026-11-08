async () => {
  await new Promise((r) => setTimeout(r, 12000));
  try { await loadGamelogs(); } catch (e) {}
  const leans = nextPropRows().map((p) => postedLean(p)).filter(Boolean);
  const plays = leans.filter((L) => L.value > 0.005);
  const nfl = (DATA.games || []).filter((g) => g.league === "nfl" && !g.completed && Date.parse(g.date) > Date.now());
  return { keepOver: pbPropKeep("over", "rec").k.toFixed(3), keepUnder: pbPropKeep("under", "rec").k.toFixed(3), keepNflTot: pbKeep("nfl", "total").k.toFixed(3),
    posted: leans.length, overPlays: plays.filter((L) => L.take === "Over").length, underPlays: plays.filter((L) => L.take === "Under").length, proven: leans.filter((L) => L.proven).length,
    nflBoard: nfl.map((g) => `${g.short_name} side ${g.proj.pick} total ${g.proj.total_pick}`), cfbRate: cfbHighRate().toFixed(4) };
}
