async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("parlay");
  const out = {};
  for (const k of ["nfl", "dogs", "favs", "totals", "cfb", "cdogs", "props"]) {
    window.__parlayLg = k; renderParlays();
    await new Promise((r) => setTimeout(r, 2500));
    window.__parlayLg = k; renderParlays();
    const h = document.getElementById("parlayHero");
    out[k] = { cards: h.querySelectorAll(".parlay-card").length, closest: !!h.querySelector(".ready-note"), text: h.innerText.slice(0, 900) };
  }
  return out;
}
