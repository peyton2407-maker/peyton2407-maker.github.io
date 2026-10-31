async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("parlay");
  const out = {};
  for (const k of ["nfl", "ml", "dogs", "favs", "totals", "cfb", "cdogs", "props"]) {
    window.__parlayLg = k; renderParlays();
    await new Promise((r) => setTimeout(r, 2500));
    window.__parlayLg = k; renderParlays();
    const h = document.getElementById("parlayHero");
    const cards = [...h.querySelectorAll(".parlay-card")];
    const txt = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
    out[k] = {
      cards: cards.length, closest: !!h.querySelector(".ready-note"),
      verdicts: cards.map((c) => txt(c.querySelector(".ready-val") || c)).reduce((a, v) => { a[v.replace(/-?\d+%/, "N%")] = (a[v.replace(/-?\d+%/, "N%")] || 0) + 1; return a; }, {}),
      placeholderPrices: cards.filter((c) => /typical price|standard price|estimated/.test(c.textContent)).length,
      nextWeekLegs: cards.filter((c) => [...c.querySelectorAll("li[data-id]")].some((li) => { const g = DATA.games.find((x) => String(x.id) === li.dataset.id); return g && !(typeof readyThisWeek === "function" ? readyThisWeek({ game_id: g.id }) : true); })).length,
      first: cards.slice(0, 2).map((c) => txt(c).slice(0, 600))
    };
  }
  return out;
}
