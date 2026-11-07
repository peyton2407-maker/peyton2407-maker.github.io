async () => {
  const url = "https://www.covers.com/sport/football/ncaaf/injuries";
  const out = {};
  for (const [name, u] of [["direct", url], ["corsproxy", "https://corsproxy.io/?" + encodeURIComponent(url)], ["allorigins", "https://api.allorigins.win/raw?url=" + encodeURIComponent(url)]]) {
    try {
      const r = await fetch(u, { cache: "no-store" });
      const t = r.ok ? await r.text() : "";
      const rows = t ? parseCoversInjuries(t) : [];
      const months = {};
      rows.forEach((x) => { const m = String(x.date || "").match(/(Aug|Sep|Oct|Nov)\w* \d+/); const k = m ? m[0] : "?"; months[k] = (months[k] || 0) + 1; });
      const latest = Object.keys(months).filter((k) => /Nov|Oct/.test(k)).sort((a, b) => Date.parse(b + " 2026") - Date.parse(a + " 2026")).slice(0, 6);
      out[name] = { status: r.status, bytes: t.length, rows: rows.length, latest: latest.map((k) => k + ": " + months[k]), age: r.headers.get("age"), date: r.headers.get("date"), lastMod: r.headers.get("last-modified") };
    } catch (e) { out[name] = "error " + String(e).slice(0, 120); }
  }
  return out;
}
