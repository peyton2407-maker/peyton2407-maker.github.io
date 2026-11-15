async () => {
  await new Promise((r) => setTimeout(r, 15000));
  try { await loadGamelogs(); } catch (e) {}
  for (let i = 0; i < 20 && !(window.PB_PROPS && window.TD_MODEL); i++) await new Promise((r) => setTimeout(r, 1000));
  let picks = [];
  try { picks = tdValueRows().map(({ r, mk, win, ev }) => `${r.name} ${pbAm(mk.off.best.odds)} ${mk.off.best.book} ${Math.round(win * 100)}% value ${(ev * 100).toFixed(1)}%`); } catch (e) { picks = ["ERR " + e]; }
  const sfx = nextPropRows().filter((p) => /\b(Jr|Sr|II|III|IV)\.?$/.test(p.name));
  return { picks, suffixPlayers: sfx.length, suffixWithPrices: sfx.filter((p) => postedLean(p)).map((p) => p.name).slice(0, 15), posted: nextPropRows().map((p) => postedLean(p)).filter(Boolean).length };
}
