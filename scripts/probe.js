async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("create");
  await new Promise((r) => setTimeout(r, 1500));
  const pl = (nextPropRows()[0] || {}).name || "";
  const last = pl.split(" ").pop();
  const qs = ["Bills -3, over 47.5, Chargers to win", "ravns and bils moneyline", `${last} under 60.5 rushing yards`, `2 leg parlay with ${pl}`, "Lamar Jackson over 220 passing", "3 leg NFL parlay at +600"];
  const out = qs.map((q) => { const s = crParseSlip(q); const d = document.createElement("div"); d.innerHTML = crLiveHtml(q); return { q, check: s.check, legs: s.legs.map((l) => l.id), live: d.textContent.replace(/\s+/g, " ") }; });
  const sug = ["rav", last.slice(0, 4).toLowerCase(), "pack"].map((q) => [q, crSuggest(q).map((x) => x.label + " | " + x.sub)]);
  createRun(qs[0]);
  await new Promise((r) => setTimeout(r, 1500));
  const take = (document.querySelector(".cr-take") || {}).textContent || "";
  createRun(qs[3]);
  await new Promise((r) => setTimeout(r, 1500));
  const notes = (document.querySelector("#createOut .cr-notes") || {}).textContent || "";
  return { pl, out, sug, take, notes };
}
