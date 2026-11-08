async () => {
  await new Promise((r) => setTimeout(r, 12000));
  try { await loadGamelogs(); } catch (e) {}
  const now = Date.now();
  const games = (DATA.games || []).filter((g) => g.league === "nfl" && !g.completed && Date.parse(g.date) > now - 3600e3 && Date.parse(g.date) < now + 3 * 864e5);
  const keys = games[0] && games[0].proj ? Object.keys(games[0].proj) : [];
  const rows = games.map((g) => {
    const p = g.proj || {}, o = g.odds || {};
    let mv = {}; try { mv = nflLineMove(g, g._lockedSpread, g._lockedTotal) || {}; } catch (e) { mv = { notes: ["ERR " + e] }; }
    const ours = -Number(p.blended_margin), tot = Number(p.blended_total != null ? p.blended_total : p.hashmark_total != null ? p.hashmark_total : p.total);
    const f = [];
    if (!Number.isFinite(ours)) f.push("margin " + p.blended_margin); if (!Number.isFinite(tot)) f.push("total missing");
    if (o.home_spread == null) f.push("no spread"); if (o.total == null) f.push("no total");
    if (Number.isFinite(ours) && o.home_spread != null && Math.abs(ours - o.home_spread) >= 3) f.push(`ours ${ours.toFixed(1)} vs line ${o.home_spread}`);
    if (Number.isFinite(tot) && o.total != null && Math.abs(tot - o.total) >= 4) f.push(`total ${tot.toFixed(1)} vs ${o.total}`);
    return `${g.short_name} ${new Date(g.date).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" })} | line ${o.home_spread}/${o.total} | ours ${ours.toFixed(1)}/${tot.toFixed(1)} | move ${(+mv.margin || 0).toFixed(1)} ${f.length ? "| FLAG " + f.join("; ") : ""}${(mv.notes || []).length ? "\n    notes: " + mv.notes.join(" / ").slice(0, 400) : ""}`;
  });
  const potd = (() => { try { const b = potdPick("nfl"); return b && `${b.g.short_name} ${b.line} ${b.price} ${b.book} hit ${Math.round(b.hit * 100)}% locked=${!!b.locked}`; } catch (e) { return "ERR " + e; } })();
  const L = window.GG_LOCKS || {};
  const lad = (L.ladder && (L.ladder.tickets || L.ladder.days || L.ladder)) || null;
  const ladTxt = (() => { try { view = "ladder"; renderLadder(); return (document.querySelector("#ladderBoard, main") || document.body).innerText.replace(/\s+/g, " ").match(/(Today's ladder|Next ladder|Ladder ticket)[^]{0,600}/)?.[0]; } catch (e) { return "ERR " + e; } })();
  const R = await propRecordPicks();
  const plays = R.picks.filter((x) => x.value > 0.005 && !x.cold && !x.thin);
  const weird = R.picks.filter((x) => !(x.chance > 0 && x.chance < 1) || !(x.books > 0 && x.books < 1) || Math.abs(x.chance - x.books) > 0.25).map((x) => `${x.name} ${x.take} ${x.line} ${x.stat} ours ${x.chance} books ${x.books}`);
  return { keys, n: games.length, rows, potd, ladTxt, props: { posted: R.picks.length, plays: plays.length, cold: R.picks.filter((x) => x.cold).length, thin: R.picks.filter((x) => x.thin).length, weird: weird.slice(0, 10) } };
}
