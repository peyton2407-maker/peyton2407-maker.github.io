async () => {
  // tonight's game as a visitor sees it
  const g = (DATA.games || []).find((x) => String(x.id) === "401873008");
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = { now: new Date().toISOString() };
  if (!g) return { err: "no game" };
  out.game = { odds: g.odds, proj: g.proj, weather: g.weather && [g.weather.condition, g.weather.temp_f, g.weather.wind_mph], injuries: (g.injuries || g.inj || []).map((r) => [r.name, r.tag, r.team]).slice(0, 30) };
  const txt = (id) => ((document.getElementById(id) || {}).innerText || "").slice(0, 2500);
  location.hash = "#nflpotd"; await sleep(5000); out.potd = txt("nflPotdSection");
  location.hash = "#nfl"; await sleep(4000);
  try { openGame("401873008"); await sleep(3000); out.sheet = ((document.getElementById("modal") || {}).innerText || "").slice(0, 3500); } catch (e) { out.sheetErr = String(e); }
  try { closeModal(); } catch (e) {}
  location.hash = "#props"; await sleep(6000);
  out.props = [...document.querySelectorAll("#propBoard .prop-card")].map((e) => e.innerText.replace(/\s+/g, " ").slice(0, 330)).filter((t) => /WSH|SF vs/.test(t)).slice(0, 14);
  out.inj = (((DATA.injuries || {}).nfl) || []).filter((r) => /Commanders|49ers/.test(r.team || "")).map((r) => [r.name, r.tag, r.team.slice(0, 12), r.gameLabel]).slice(0, 40);
  return out;
}
