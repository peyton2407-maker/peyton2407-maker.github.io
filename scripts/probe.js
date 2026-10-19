async () => {
  // what a visitor sees for injuries and weather: where the numbers came from and how old
  const pack = (typeof ensureInjPack === "function") ? ensureInjPack() : {};
  const up = (DATA.games || []).filter((g) => !g.completed && g.date && Date.parse(g.date) > Date.now() - 4 * 3600e3 && Date.parse(g.date) < Date.now() + 3 * 86400e3);
  let file = null;
  try { file = await (await fetch("/data/eleven.json?t=" + Date.now())).json(); } catch (e) {}
  return {
    now: new Date().toISOString(),
    pack: { nfl: (pack.nfl || []).length, cfb: (pack.cfb || []).length, nflLive: pack.nflLive, cfbLive: pack.cfbLive, nflReport: pack.nflReport, cfbReport: pack.cfbReport, fetched: pack.fetched ? new Date(pack.fetched).toISOString() : null },
    file: file ? { label: file.label, ymd: file.ymd, nfl: (file.nfl || []).length, wxNfl: (file.wxNfl || []).length, wxCfb: (file.wxCfb || []).length } : null,
    stamp: (document.getElementById("stamp") || {}).textContent,
    games: up.slice(0, 12).map((g) => ({ g: g.short_name, lg: g.league, date: g.date, wx: g.weather ? [g.weather.condition, g.weather.temp_f, g.weather.wind_mph, g.weather.fetched || g.weather.at || null] : null, inj: (g.injuries || g.inj || []).length })),
    injView: ((document.getElementById("injBoard") || document.querySelector("#nflinjSection") || {}).innerText || "").slice(0, 1500),
  };
}
