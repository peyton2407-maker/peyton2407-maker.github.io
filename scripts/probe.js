async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("parlay");
  await new Promise((r) => setTimeout(r, 1500));
  const txt = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
  const out = {};
  for (const k of ["nfl", "ml", "dogs", "favs", "totals", "props"]) {
    window.__parlayLg = k; renderParlays();
    await new Promise((r) => setTimeout(r, 2000));
    window.__parlayLg = k; renderParlays();
    const cards = [...document.querySelectorAll("#parlayHero .parlay-card")];
    const kicks = new Set();
    cards.forEach((c) => c.querySelectorAll("li[data-id]").forEach((li) => { const g = DATA.games.find((x) => String(x.id) === li.dataset.id); if (g) kicks.add(g.short_name + " " + g.date.slice(11, 16) + "Z" + (Date.parse(g.date) <= Date.now() ? " STARTED" : "")); }));
    out[k] = {
      cards: cards.length, closest: !!document.querySelector("#parlayHero .ready-note"),
      verdicts: cards.map((c) => txt(c.querySelector(".ready-val") || c).replace(/[-+]?\d+%/, "N%")).reduce((a, v) => (a[v] = (a[v] || 0) + 1, a), {}),
      games: [...kicks].slice(0, 30), first: cards.slice(0, 2).map((c) => txt(c).slice(0, 420))
    };
  }
  out.best = [...document.querySelectorAll("#parlayBest .parlay-card")].map((c) => txt(c).slice(0, 420));
  setView("card"); await new Promise((r) => setTimeout(r, 800));
  out.card = (document.getElementById("view-card") || document.querySelector(".content") || document.body).innerText.slice(0, 900);
  return out;
}
