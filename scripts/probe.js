async () => {
  await new Promise((r) => setTimeout(r, 10000));
  const main = document.querySelector("main") || document.body;
  const t = main.innerText || "";
  const bad = (t.match(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%/g) || []);
  const ctx = bad.length ? t.slice(Math.max(0, t.search(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%/) - 120), t.search(/\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|null%/) + 60).replace(/\s+/g, " ") : "";
  const n = document.getElementById("cfbInjStale");
  return { chars: t.length, bad: bad.length, ctx, empty: /Nothing here|No games|couldn't load|failed to load|Loading…$/i.test(t.trim().slice(-200)), stale: n && n.style.display !== "none" ? n.textContent.slice(0, 200) : "", updating: /Updating…/.test(t.slice(0, 40)) };
}
