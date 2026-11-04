async () => {
  // the touchdown page as drawn: the rows it ranks, with the market reading and the checked chance
  const rows = collectTdBoard(), MK = tdMarketMap(rows), keep = pbKeep("nfl", "td").k;
  const out = [];
  rows.forEach((r) => { const mk = MK.get(r.game_id + "|" + r.id); if (!mk) return; const win = mk.mkt + keep * (r.anytime - mk.mkt); out.push({ name: r.name, team: r.team, ours: +r.anytime.toFixed(3), mkt: +mk.mkt.toFixed(3), win: +win.toFixed(3), best: mk.off.best.odds, book: mk.off.best.book, ev: +(win * pbDec(mk.off.best.odds) - 1).toFixed(3) }); });
  out.sort((a, b) => b.ev - a.ev);
  return { keep, priced: out.length, positive: out.filter((x) => x.ev > 0).length, over3: out.filter((x) => x.ev >= 0.03).length, top: out.slice(0, 25), bottom: out.slice(-5) };
}
