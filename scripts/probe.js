async () => {
  try { await ensurePotdProps(); } catch (e) {}
  const rows = nextPropRows();
  const lam = rows.filter((p) => /lamar|jackson/i.test(p.name || "")).map((p) => ({ id: p.id, name: p.name, game: p.game_id, date: p.date, inj: p.injury, lean: (() => { try { const L = postedLean(p); return L && { k: L.m.key, line: L.line, take: L.take, price: L.price, fair: L.fair, tid: propTicketId(p, L) }; } catch (e) { return String(e); } })() }));
  let priced = 0, withTid = 0;
  rows.forEach((p) => { try { const L = postedLean(p); if (L && L.price != null && L.fair != null) { priced++; if (propTicketId(p, L)) withTid++; } } catch (e) {} });
  const all = collectNflProps();
  const w = createParse("2 leg parlay with Lamar Jackson");
  return { all: all.length, next: rows.length, priced, withTid, lam, players: w.players, sample: rows.slice(0, 5).map((p) => [p.name, p.date, p.game_id]), dk: typeof window.__DK_LINES !== "undefined" ? Object.keys(window.__DK_LINES || {}).length : "n/a" };
}
