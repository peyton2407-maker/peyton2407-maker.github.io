async () => {
  await new Promise((r) => setTimeout(r, 6000));
  try { await loadGamelogs(); } catch (e) {}
  const R = await propRecordPicks();
  const plays = R.picks.filter((x) => x.value > 0.005);
  return {
    picks: R.picks.length, withLast8: R.picks.filter((x) => x.last8).length, plays: plays.length,
    cold: R.picks.filter((x) => x.cold).map((x) => `${x.name} ${x.take} ${x.line} ${x.stat} ${x.last8} value ${x.value}`),
    ladderLegs: collectPropParlayLegs().map((l) => l.label),
    charts: [...document.querySelectorAll(".pick-hist .ph-head")].map((e) => e.innerText.replace(/\s+/g, " ").slice(0, 90)),
  };
}
