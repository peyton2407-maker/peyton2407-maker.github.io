async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = {};
  const g = (DATA.games || []).find((x) => x.short_name === "BAL @ BUF" && !x.completed);
  if (g) { const h = pbLeg({ id: g.id + "|sp|home" }), a = pbLeg({ id: g.id + "|sp|away" }); out.buf = [h.label, h.price, +h.bookWin.toFixed(3), a.label, a.price, +a.bookWin.toFixed(3)]; }
  location.hash = "#parlay"; await sleep(5000);
  for (const t of ["nfl", "favs", "cfb", "cdogs"]) { window.__parlayLg = t; renderParlays(); await sleep(800); out[t] = (document.getElementById("parlayHero").innerText || "").replace(/\s+/g, " ").slice(0, 260); }
  return out;
}
