async () => {
  const out = {};
  try {
    const cfb = await getJSON(injEndpoint("/apis/site/v2/sports/football/college-football/injuries"));
    const rows = parseInjuryFeed(cfb, "cfb");
    const days = {};
    rows.forEach((r) => { const k = String(r.date || "").slice(0, 10) || "?"; days[k] = (days[k] || 0) + 1; });
    out.espn = { rows: rows.length, teams: new Set(rows.map((r) => r.team)).size, days: Object.entries(days).sort().slice(-10), qbs: rows.filter((r) => String(r.pos).toUpperCase() === "QB").map((r) => `${r.name} ${r.team} ${r.tag || r.status} ${String(r.date || "").slice(0, 10)}`).slice(0, 25) };
  } catch (e) { out.espn = "error " + e; }
  try { const n = await pullCfbInjuryNews(); out.news = { rows: (n || []).length, sample: (n || []).slice(0, 8).map((r) => `${r.name} ${r.team} ${r.tag} ${String(r.date || "").slice(0, 10)}`) }; } catch (e) { out.news = "error " + e; }
  return out;
}
