async () => {
  try { await ensurePotdProps(); } catch (e) {}
  setView("create");
  await new Promise((r) => setTimeout(r, 1200));
  const qs = ["2 leg parlay with Lamar Jackson", "3 leg NFL parlay at +600", "Sunday player prop unders", "College moneyline parlay Saturday", "Safest 2 leg parlay this weekend"];
  const out = [];
  for (const q of qs) {
    const want = createParse(q);
    const t = createTickets(want) || [];
    out.push({ q, understood: (document.createElement("div").innerHTML = createUnderstood(want), want.players && want.players.map((p) => p.name || p)), tickets: t.slice(0, 3).map((k) => [k.american, (k.legs || []).map((l) => l.label).join(" + "), k.ev]) });
  }
  const inp = document.querySelector(".cr-form input");
  inp.value = qs[0]; inp.form.requestSubmit();
  await new Promise((r) => setTimeout(r, 1500));
  return { props: (window.__WEEK_PLAYERS || []).length, out, text: (document.getElementById("createOut").textContent || "").replace(/\s+/g, " ").slice(0, 700) };
}
