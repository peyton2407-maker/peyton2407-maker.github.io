async () => {
  try { await ensurePotdProps(); } catch (e) {}
  const rows = nextPropRows();
  const by = {};
  rows.forEach((p) => ["pass_yds", "pass_td", "rush_yds", "rush_att", "rec_yds", "rec"].forEach((k) => { const a = propOppAdj(p, k); if (!a) return; const b = by[k] = by[k] || { n: 0, moved: 0, max: 0, withTargets: 0 }; b.n++; if (Math.abs(a.f - 1) >= 0.02) b.moved++; b.max = Math.max(b.max, Math.abs(a.f - 1)); if (a.parts.some((x) => x.stat === "targets" || x.stat === "rush_att")) b.withTargets++; }));
  const notes = [];
  for (const p of rows) { for (const k of ["rec", "rec_yds", "rush_yds"]) { const n = propOppNote(p, k); if (n && /targets|carries/.test(n)) { notes.push(p.name + " (" + k + "): " + n); break; } } if (notes.length >= 3) break; }
  return { props: rows.length, by, notes };
}
