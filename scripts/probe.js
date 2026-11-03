async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("create");
  await new Promise((r) => setTimeout(r, 1500));
  const A = ["$20 to win $200", "Sunday night only", "parlay without the Chiefs", "fade the Chiefs 2 leg", "around even money NFL"].map((q) => { const w = createParse(q); const res = createTickets(w); return [q, w.legs, w.target, w.hours, (w.exclude || []).map((t) => t.abbr), (w.fade || []).map((t) => t.abbr), res.pool.length, res.shrunk, res.tickets.map((t) => [t.x.r.american, t.bag.map((l) => l.label).join(" + ")])]; });
  const B = ["Bills -3 or Bills to win?", "Lions game over 51 or under", "Bills or Ravens"].map((q) => { const c = crParseCompare(q); return [q, c && c.map((s) => s.ids.join("+"))]; });
  createRun("Bills -3 or Bills to win?");
  await new Promise((r) => setTimeout(r, 1500));
  const take = (document.querySelector(".cr-take") || {}).textContent || "";
  const table = (document.querySelector(".cr-cmp") || {}).textContent || "";
  return { A, B, take, table: table.replace(/\s+/g, " ").slice(0, 600) };
}
