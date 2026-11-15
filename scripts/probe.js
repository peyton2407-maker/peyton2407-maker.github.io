async () => {
  await new Promise((r) => setTimeout(r, 15000));
  try { setView("tds"); } catch (e) {}
  await new Promise((r) => setTimeout(r, 5000));
  const bad = performance.getEntriesByType("resource").filter((e) => e.responseStatus >= 400).map((e) => e.responseStatus + " " + e.name.split("?")[0].slice(0, 120));
  const hosts = {}; bad.forEach((b) => { const h = b.split(" ")[1].split("/")[2]; hosts[h] = (hosts[h] || 0) + 1; });
  return { bad: bad.slice(0, 12), hosts };
}
