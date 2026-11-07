async () => {
  const out = {};
  const tries = {
    cbs: "https://www.cbssports.com/college-football/injuries/",
    rotowire: "https://www.rotowire.com/cfootball/injury-report.php",
    espnCoreTeam: "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/teams/333/injuries?limit=50",
    espnSummary: "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=" + ((DATA.games || []).find((g) => g.league === "cfb" && !g.completed && Date.parse(g.date) > Date.now()) || {}).id,
    covers2: "https://www.covers.com/sport/football/ncaaf/injuries?_=" + Date.now(),
  };
  for (const [k, u] of Object.entries(tries)) {
    try {
      const r = await fetch(u, { cache: "no-store" });
      const t = r.ok ? await r.text() : "";
      const nov = (t.match(/Nov(?:ember|\.)?\s+[1-7]\b|11\/0?[1-7]\/(?:20)?26|2026-11-0[1-7]/g) || []).length;
      const oct = (t.match(/Oct(?:ober|\.)?\s+\d+|10\/\d+\/(?:20)?26|2026-10-\d\d/g) || []).length;
      let extra = "";
      if (k === "espnCoreTeam") { try { extra = JSON.stringify(JSON.parse(t)).slice(0, 300); } catch (e) {} }
      if (k === "espnSummary") { try { const j = JSON.parse(t); extra = JSON.stringify((j.injuries || []).map((x) => (x.injuries || []).length)); } catch (e) {} }
      if (k === "cbs" || k === "rotowire") { const i = t.search(/Nov(?:ember|\.)?\s+[1-7]\b/); extra = i > 0 ? t.slice(i - 300, i + 100).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ") : t.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(2000, 2300); }
      out[k] = { status: r.status, bytes: t.length, novMentions: nov, octMentions: oct, extra };
    } catch (e) { out[k] = "error " + String(e).slice(0, 100); }
  }
  return out;
}
