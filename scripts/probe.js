async () => {
  await new Promise((r) => setTimeout(r, 9000));
  const now = Date.now();
  const games = (DATA.games || []).filter((g) => g.league === "cfb" && !g.completed && Date.parse(g.date) > now - 4 * 3600e3 && g.proj && g.proj.split_locked);
  const moved = games.map((g) => ({ g: g.short_name, split: +(-g.proj.split_margin).toFixed(1), ours: g.proj.hashmark_home_spread, line: g.odds && g.odds.home_spread,
      diff: +(g.proj.blended_margin - g.proj.split_margin).toFixed(1), notes: (cfbLineMove(g, g._lockedSpread, g._lockedTotal).notes || []).join(" | ").slice(0, 260) }))
    .filter((x) => Math.abs(x.diff) >= 2).sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff));
  const bad = (DATA.games || []).filter((g) => g.proj && ["blended_margin", "hashmark_total"].some((k) => g.proj[k] != null && !Number.isFinite(Number(g.proj[k])))).map((g) => g.short_name);
  return { cfbUpcoming: games.length, movedOver2: moved.length, moved: moved.slice(0, 15), nonNumeric: bad,
    picksPage: (document.querySelector("#view-cfbpicks, main") || document.body).innerText.replace(/\s+/g, " ").slice(0, 1500) };
}
