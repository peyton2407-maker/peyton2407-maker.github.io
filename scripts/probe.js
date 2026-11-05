async () => ({ hero: [...document.querySelectorAll(".td-hero-card")].map((c) => c.innerText.replace(/\n/g, " | ")), stats: (document.getElementById("tdStats") || {}).innerText })
