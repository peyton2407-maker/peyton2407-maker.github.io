async () => {
  try { await ensurePotdProps(); } catch (e) {}
  window.__ladderLive = null;
  setView("ladder");
  await new Promise((r) => setTimeout(r, 1500));
  const cur = ladderCurrent();
  const pool = cur ? ladderLegPool(cur.row.day).map((l) => [l.label, l.cat, +(l._v * 100).toFixed(1)]) : [];
  const box = document.getElementById("ladderBoard");
  return { cur: cur && { live: cur.live, day: cur.row.day, book: cur.row.book, american: cur.row.american, ev: cur.row.ev, chance: cur.row.chance, legs: cur.row.legs.map((l) => [l.label, l.price, l.cat, l.value]) }, pool, text: (box.textContent || "").replace(/\s+/g, " ").slice(0, 900) };
}
