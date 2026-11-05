async () => {
  await new Promise((r) => setTimeout(r, 6000));
  return [...document.querySelectorAll(".pick-hist")].map((e) => (e.querySelector(".ph-head") || e).innerText.replace(/\s+/g, " ").slice(0, 120));
}
