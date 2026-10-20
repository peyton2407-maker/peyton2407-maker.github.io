async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const txt = (sel) => ((document.querySelector(sel) || {}).innerText || "").replace(/\s+/g, " ").slice(0, 900);
  const out = { now: new Date().toISOString(), stamp: txt("#stamp"), tabs: [...document.querySelectorAll('a.tab')].map((a) => a.textContent.trim()).slice(0, 12) };
  out.home = txt("#homeSection");
  location.hash = "#nfl"; await sleep(4000); out.nfl = txt("#boardSection");
  location.hash = "#score"; await sleep(4000); out.score = txt("#scoreSection");
  location.hash = "#props"; await sleep(6000); out.props = txt("#propStats");
  location.hash = "#nflinj"; await sleep(4000); out.inj = txt("#injStamp") + " | " + txt("#cfbInjWeek");
  location.hash = "#cfbpicks"; await sleep(4000); out.cfb = txt("#cfbPicksSection");
  out.week = typeof currentNflWeekNumber === "function" ? currentNflWeekNumber() : null;
  return out;
}
