async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("create");
  await new Promise((r) => setTimeout(r, 1200));
  const qs = ["2 leg parlay with Lamar Jackson", "3 leg NFL parlay at +600", "Sunday player prop unders", "College moneyline parlay Saturday", "Safest 2 leg parlay this weekend"];
  const out = [];
  for (const q of qs) {
    const want = createParse(q);
    const res = createTickets(want);
    out.push({ q, players: want.players.map((p) => p.name), teams: want.teams.map((t) => t.abbr), pool: res.pool.length, tickets: res.tickets.map((k) => [k.x.r.american, k.x.book, Math.round(k.x.r.ev * 100), k.bag.map((l) => l.label).join(" + ")]) });
  }
  const inp = document.getElementById("createInput");
  inp.value = qs[0]; createRun(qs[0]);
  await new Promise((r) => setTimeout(r, 1500));
  const facts = [...document.querySelectorAll(".cr-ticket")].slice(0, 1).map((c) => c.textContent.replace(/\s+/g, " ").slice(0, 1500));
  return { props: (window.__WEEK_PLAYERS || []).length, out, facts };
}
