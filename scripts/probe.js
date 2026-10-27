async () => {
  const picks = (DATA.games || []).filter((g) => g && !g.completed && g.proj).map((g) => [g.short_name, (shownPick(g) || {}).side || "-", g.proj.hashmark_home_spread, g.proj.total_pick]);
  const f = document.getElementById("homeFilter");
  return { width: innerWidth, deployed: !String(cfbRestTravel).includes("cfbLearnNudge") && document.body.innerHTML.includes("Picks only"),
    hero: (document.querySelector("#homeFeature") || {}).innerText ? document.querySelector("#homeFeature").innerText.slice(0, 160) : null,
    filterH: f ? Math.round(f.getBoundingClientRect().height) : null, filterW: f ? f.scrollWidth - f.clientWidth : null, picks };
}
