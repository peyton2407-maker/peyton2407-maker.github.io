async () => {
  await new Promise((r) => setTimeout(r, 15000));
  try { await loadGamelogs(); } catch (e) {}
  for (let i = 0; i < 20 && !(window.PB_PROPS && window.TD_MODEL); i++) await new Promise((r) => setTimeout(r, 1000));
  let picks = [];
  try { picks = tdValueRows().map(({ r, mk, win, ev }) => `${r.name} ${r.pos} ${r.team} ${pbAm(mk.off.best.odds)} ${mk.off.best.book} ${Math.round(win * 100)}% value ${(ev * 100).toFixed(1)}% ${new Date(r.date).toLocaleString("en-US", { weekday: "short", hour: "numeric", timeZone: "America/New_York" })}`); } catch (e) { picks = ["ERR " + e]; }
  try { setView("tds"); } catch (e) {}
  await new Promise((r) => setTimeout(r, 4000));
  const hero = [...document.querySelectorAll("#tdHero .td-hero-card")].map((e) => e.innerText.replace(/\s+/g, " ").slice(0, 160));
  const rec = (document.getElementById("tdRecord") || {}).innerText || "";
  const top = [...document.querySelectorAll(".tdl-row summary")].slice(0, 8).map((e) => e.innerText.replace(/\s+/g, " ").slice(0, 120));
  return { model: !!window.TD_MODEL, picks, hero, rec: rec.replace(/\s+/g, " ").slice(0, 600), top, bad: ((document.querySelector("main") || document.body).innerText.match(/\bNaN\b|\bundefined\b/g) || []).length };
}
