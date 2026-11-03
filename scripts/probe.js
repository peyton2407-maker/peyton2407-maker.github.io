async () => {
  setView("ladder");
  await new Promise((r) => setTimeout(r, 2500));
  const cur = ladderCurrent();
  const rows = ladderRows().map((r) => [r.key, r.locked, r.provisional, r.american, r.legs.map((l) => l.label).join(" + ")]);
  let next = null;
  try { const pick = ladderBuild(new Set(ladderRows().filter((r) => r.locked).map((r) => r.day))); next = pick ? ladderRow(pick) : null; } catch (e) { next = String(e); }
  const box = document.getElementById("ladderBoard") || document.getElementById("ladderSection");
  return { cur: cur && { live: cur.live, key: cur.row.key, locked: cur.row.locked }, rows, next: next && (typeof next === "string" ? next : { key: next.key, day: next.day, first: next.firstKick, legs: next.legs.map((l) => l.label) }), text: (box && box.textContent || "").replace(/\s+/g, " ").slice(0, 500) };
}
