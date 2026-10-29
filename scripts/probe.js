async () => {
  const out = { width: innerWidth, now: new Date().toISOString() };
  const safe = (f) => { try { return f(); } catch (e) { return "ERR " + e.message; } };
  out.nflPotd = safe(() => { const b = potdPick("nfl"); return b ? [b.g.short_name, b.kind, b.line, b.price, Math.round((b.ev || 0) * 1000) / 10, b.label] : null; });
  out.cfbPotd = safe(() => { const b = potdPick("cfb"); return b ? [b.g.short_name, b.kind, b.line, b.label] : null; });
  out.tnfCands = safe(() => { const g = DATA.games.find((x) => x.short_name === "CAR @ GB"); return g ? potdNflCandidates(g).map((b) => [b.kind, b.line, b.price, Math.round(b.ev * 1000) / 10]).slice(0, 12) : "no game"; });
  out.tnf = safe(() => { const g = DATA.games.find((x) => x.short_name === "CAR @ GB"); return g ? { odds: g.odds && [g.odds.details, g.odds.total], proj: [g.proj.away_points, g.proj.home_points, g.proj.pick_line, g.proj.total_pick], shown: shownPick(g), wx: g.weather && [g.weather.temp_f, g.weather.wind_mph], inj: (g.injuries || []).length } : null; });
  out.tallies = safe(() => ["nfl", "cfb"].map((l) => { const t = potdTally(potdPublished(l)); return [l, t.hit, t.n - t.hit, t.units]; }));
  out.cardText = safe(() => { setView("card"); return document.querySelector("main").innerText.slice(0, 900); });
  out.potdText = safe(() => { setView("potd"); return document.querySelector("main").innerText.slice(0, 1400); });
  out.nflpotdText = safe(() => { setView("nflpotd"); return document.querySelector("main").innerText.slice(0, 1400); });
  out.consoleErrors = window.__probeErrs || null;
  return out;
}
