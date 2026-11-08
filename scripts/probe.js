async () => {
  await new Promise((r) => setTimeout(r, 14000));
  const t = (document.querySelector("main") || document.body).innerText;
  const grab = (re) => (t.match(re) || []).slice(0, 4);
  return {
    proven: (t.match(/Proven pick:/g) || []).length, wrong: (t.match(/Wrong matchup for this side:/g) || []).length,
    helps: (t.match(/Matchup helps:/g) || []).length, mid: (t.match(/Matchup: /g) || []).length,
    samples: grab(/(Wrong matchup for this side|Matchup helps)[^\n]{0,220}/g),
    potd: grab(/Patrick Mahomes under 2\.5[^\n]{0,300}/g), bad: (t.match(/\bNaN\b|\bundefined\b|\[object Object\]/g) || []).length,
  };
}
