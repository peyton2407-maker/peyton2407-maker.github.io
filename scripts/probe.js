() => {
  const g = DATA.games.find((x) => x.short_name === "CAR @ GB");
  const b = g.box || {};
  const pick = (n) => (g.props || []).find((p) => p.name === n);
  const yg = pick("Bryce Young"), kr = pick("Tucker Kraft"), cw = pick("Christian Watson");
  const lean = (p) => { try { const x = p && postedLean(collectNflProps().find((q) => String(q.id) === String(p.id))); return x && [x.take, x.line, x.m.key, Math.round(x.m.mean * 10) / 10, Math.round(x.chance * 1000) / 10, Math.round(x.fair * 1000) / 10, Math.round((x.value || 0) * 1000) / 10]; } catch (e) { return "ERR " + e.message; } };
  return {
    box: [b.home_rush_yds, b.home_rec_yds, b.away_rush_yds, b.away_rec_yds], proj: [g.proj.away_points, g.proj.home_points],
    props: (g.props || []).length, keep: (() => { try { return pbKeep("nfl", "props").k; } catch (e) { return null; } })(),
    cal: !!window.PB_CAL, pbProps: !!window.PB_PROPS, logs: !!window.GAMELOGS, inj: (((DATA.injuries || {}).nfl) || []).length, eleven: typeof __elevenSaved !== "undefined" ? __elevenSaved : null,
    young: yg && [yg.rush_yds, yg.injury || ""], kraft: kr && [kr.rec_yds, kr.injury || ""], watson: cw && [cw.rec_yds, cw.injury || ""],
    leanYoung: lean(yg), leanKraft: lean(kr), leanWatson: lean(cw),
    potd: (() => { globalThis.__potdRepick = true; try { const f = potdPick("nfl"); return f && [f.line, Math.round((f.ev || 0) * 1000) / 10]; } finally { globalThis.__potdRepick = false; } })()
  };
}
