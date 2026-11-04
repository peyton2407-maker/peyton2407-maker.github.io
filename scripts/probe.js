async () => {
  try { await ensurePotdProps(); } catch (e) {}
  const rows = nextPropRows();
  const adj = [];
  rows.forEach((p) => ["pass_yds", "rush_yds", "rec_yds", "rec", "pass_td"].forEach((k) => { const a = propOppAdj(p, k); if (a) adj.push([p.name, p.opp, k, +a.f.toFixed(3), +a.raw.toFixed(2), a.n]); }));
  adj.sort((a, b) => Math.abs(b[3] - 1) - Math.abs(a[3] - 1));
  const fs = adj.map((x) => x[3]);
  const note = (() => { for (const p of rows) { for (const k of ["rec_yds", "rush_yds", "pass_yds"]) { const n = propOppNote(p, k); if (n) return p.name + ": " + n; } } return ""; })();
  setView("score");
  await new Promise((r) => setTimeout(r, 2500));
  return { props: rows.length, logs: !!window.GAMELOGS, adjusted: adj.length, moved: fs.filter((f) => Math.abs(f - 1) >= 0.02).length, capped: fs.filter((f) => Math.abs(f - 1) >= 0.149).length, avg: fs.length ? +(fs.reduce((a, x) => a + x, 0) / fs.length).toFixed(3) : null, top: adj.slice(0, 8), note, proof: (document.getElementById("proofBox").textContent || "").replace(/\s+/g, " ").slice(0, 900) };
}
