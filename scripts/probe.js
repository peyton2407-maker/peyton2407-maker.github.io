async () => {
  await new Promise((r) => setTimeout(r, 12000));
  const now = Date.now();
  const desk = window.SPLIT_DESK || [];
  const ids = new Set((DATA.games || []).filter((g) => g.league === "cfb").map((g) => String(g.id)));
  const out = { deskRows: desk.length, deskUnmatched: desk.filter((r) => !ids.has(String(r.id))).map((r) => `${r.away} @ ${r.home} (${r.id})`).slice(0, 15) };
  const week = (DATA.games || []).filter((g) => g.league === "cfb" && Math.abs(Date.parse(g.date) - now) < 4 * 864e5);
  const up = week.filter((g) => !g.completed && Date.parse(g.date) > now);
  out.weekGames = week.length; out.upcoming = up.length; out.final = week.filter((g) => g.completed).length;
  const flags = [];
  up.forEach((g) => {
    const p = g.proj || {}, o = g.odds || {};
    const f = [];
    if (!p.split_locked) f.push("no Split row");
    ["hashmark_total", "blended_margin", "home_points", "away_points"].forEach((k) => { if (!Number.isFinite(Number(p[k]))) f.push(k + "=" + p[k]); });
    if (o.home_spread == null) f.push("no spread"); if (o.total == null) f.push("no total");
    if (Number.isFinite(+p.blended_margin) && o.home_spread != null && Math.abs(-p.blended_margin - o.home_spread) > 10) f.push(`ours ${(-p.blended_margin).toFixed(1)} vs line ${o.home_spread}`);
    if (Number.isFinite(+p.hashmark_total) && o.total != null && Math.abs(p.hashmark_total - o.total) > 8) f.push(`total ours ${p.hashmark_total} vs ${o.total}`);
    if (Math.abs((+p.home_points + +p.away_points) - p.hashmark_total) > 0.6) f.push("points don't add up to total");
    if (p.edge_total != null && p.total_pick && (Math.abs(p.edge_total) < 1.5) !== (p.total_pick === "NO PLAY")) f.push(`total pick ${p.total_pick} vs edge ${p.edge_total}`);
    if (f.length) flags.push(`${g.short_name}: ${f.join("; ")}`);
  });
  out.flags = flags;
  out.plays = up.map((g) => ({ g, a: cfbAngleFor(g) })).filter((x) => x.a && x.a.play).map(({ g, a }) => `${g.short_name} ${a.play.line} ${pbAm(a.play.price)} ${a.play.book || ""} hit ${Math.round(a.play.hit * 100)}% ev ${(a.play.ev * 100).toFixed(1)}% [${a.play.angle}] mkt total ${(g.odds || {}).total}`);
  out.potd = (() => { try { const b = potdPick("cfb"); return b ? `${b.game || (b.g && b.g.short_name)} ${b.line} ${b.price} locked=${!!b.locked}` : null; } catch (e) { return "error " + e; } })();
  out.liveOdd = week.filter((g) => !g.completed && Date.parse(g.date) < now - 5 * 3600e3).map((g) => g.short_name + " still not final " + g.date);
  out.scoreCfb = (() => { try { view = "score"; renderScorecard(); return (document.querySelector("main") || document.body).innerText.replace(/\s+/g, " ").match(/College[^.]{0,300}/g)?.slice(0, 4); } catch (e) { return "error " + e; } })();
  return out;
}
