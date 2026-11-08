async () => {
  await new Promise((r) => setTimeout(r, 12000));
  try { await loadGamelogs(); } catch (e) {}
  const out = { tiers: !!window.DEF_TIERS, through: window.DEF_TIERS && window.DEF_TIERS.through_week };
  const rows = nextPropRows();
  const leans = rows.map((p) => ({ p, L: postedLean(p) })).filter((x) => x.L);
  out.posted = leans.length;
  out.proven = leans.filter((x) => x.L.proven).map(({ p, L }) => `${p.name} (${p.team} v ${p.opp}) under ${L.line} ${L.m.key} ch ${Math.round(L.chance * 100)} books ${Math.round(L.fair * 100)} ${pbAm(L.price)} ${L.def ? L.def.tier + " #" + L.def.rank : "no tier"} ${p.game} ${new Date(p.date).toLocaleString("en-US", { weekday: "short", hour: "numeric", timeZone: "America/New_York" })}`);
  out.againstUnders = leans.filter((x) => x.L.take === "Under" && x.L.defAgainst && x.L.value > 0.005).length;
  out.bigEdgeUnders = leans.filter((x) => x.L.take === "Under" && x.L.gap > PROP_EDGE_MAX && x.L.value > 0.005).length;
  try { const b = potdPick("nfl"); out.potd = b && `${b.g.short_name} ${b.line} ${pbAm(b.price)} ${b.book} hit ${Math.round(b.hit * 100)}% locked=${!!b.locked} proven=${!!b.proven} | ${b.why}`; } catch (e) { out.potd = "ERR " + e; }
  try { const t = ladderBuild(new Set(ladderRows().filter((r) => r.locked || r.result).map((r) => r.day))); out.ladderNext = t ? `${t.day} ${t.x.book || ""} pAll ${Math.round(t.x.r.pAll * 100)}% ev ${(t.x.r.ev * 100).toFixed(1)}% :: ` + t.legs.map((l) => l.label + " [" + l.cat + "]").join(" | ") : "no ticket"; } catch (e) { out.ladderNext = "ERR " + e; }
  try { const L = ggLockRun(window.GG_LOCKS || {}); out.lockRun = (L.changes || []).slice(0, 8); } catch (e) { out.lockRun = "ERR " + e; }
  return out;
}
