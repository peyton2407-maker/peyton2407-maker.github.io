async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("parlay");
  await new Promise((r) => setTimeout(r, 1500));
  window.__parlayLg = "nfl"; renderParlays();
  await new Promise((r) => setTimeout(r, 2000));
  window.__parlayLg = "nfl"; renderParlays();
  const txt = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
  const best = [...document.querySelectorAll("#parlayBest .parlay-card")].map((c) => txt(c).slice(0, 700));
  const out = { best };
  for (const k of ["ml", "favs", "props", "cfb"]) {
    window.__parlayLg = k; renderParlays();
    await new Promise((r) => setTimeout(r, 1500));
    const cards = [...document.querySelectorAll("#parlayHero .parlay-card")];
    out[k] = { cards: cards.length, top: cards.slice(0, 2).map((c) => txt(c).slice(0, 300)) };
  }
  return out;
}
