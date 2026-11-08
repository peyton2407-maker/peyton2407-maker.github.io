async () => {
  await new Promise((r) => setTimeout(r, 12000));
  const chips = [...document.querySelectorAll(".es-chip")].map((e) => e.innerText).slice(0, 12);
  return { chips: chips.length, sample: chips, bad: ((document.querySelector("main") || document.body).innerText.match(/\bNaN\b|\bundefined\b/g) || []).length };
}
