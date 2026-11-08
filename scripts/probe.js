async () => {
  const views = ["home","all","nfl","cfb","cfbpicks","potd","nflpotd","ladder","props","tds","parlay","builder","calc","card","bets","value","prime","live","charts","ratings","season","history","heisman","recruit","nflinj","cfbinj","nflwx","cfbwx","score"];
  const errs = [];
  window.addEventListener("error", (e) => errs.push(String(e.message).slice(0, 160)));
  window.addEventListener("unhandledrejection", (e) => errs.push("promise: " + String(e.reason).slice(0, 160)));
  const oerr = console.error; console.error = (...a) => { errs.push("console: " + a.map(String).join(" ").slice(0, 160)); oerr.apply(console, a); };
  await new Promise((r) => setTimeout(r, 8000));
  const out = {};
  for (const v of views) {
    const before = errs.length;
    const t0 = performance.now();
    try { setView(v); } catch (e) { errs.push(v + " setView: " + e); }
    await new Promise((r) => setTimeout(r, 3500));
    const sec = document.querySelector(`#view-${v}, [data-view-panel="${v}"], section.view.active, main`) || document.body;
    const vis = [...document.querySelectorAll("section, .view")].find((el) => el.offsetParent !== null && el.innerText.length > 200) || sec;
    const t = (document.querySelector("main") || document.body).innerText;
    const bad = (t.match(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%|\bnull\b(?= ?(pts|u\b|%))/g) || []);
    const badCtx = bad.length ? t.slice(Math.max(0, t.search(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%/) - 100), t.search(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%/) + 50).replace(/\s+/g, " ") : "";
    const loading = (t.match(/Loading…|Loading\.\.\./g) || []).length;
    const wide = [...document.querySelectorAll("main *")].filter((el) => el.offsetParent !== null && el.getBoundingClientRect().right > window.innerWidth + 2).slice(0, 3).map((el) => el.tagName + "." + String(el.className).slice(0, 40) + " w" + Math.round(el.getBoundingClientRect().right));
    out[v] = { chars: t.length, ms: Math.round(performance.now() - t0), bad: bad.length, badCtx, loading, errs: errs.slice(before), wide };
  }
  const res = performance.getEntriesByType("resource").map((r) => ({ n: r.name.replace(location.origin, "").split("?")[0], kb: Math.round((r.transferSize || r.encodedBodySize || 0) / 1024), ms: Math.round(r.duration) }));
  const agg = {};
  res.forEach((r) => { const a = agg[r.n] || (agg[r.n] = { kb: 0, n: 0, ms: 0 }); a.kb += r.kb; a.n++; a.ms = Math.max(a.ms, r.ms); });
  out._resources = Object.entries(agg).sort((a, b) => b[1].kb - a[1].kb).slice(0, 25);
  out._dupFetches = Object.entries(agg).filter(([k, v]) => v.n > 2 && k.includes("/data/")).map(([k, v]) => k + " x" + v.n);
  return out;
}
