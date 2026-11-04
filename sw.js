// Double Gs service worker: faster repeat visits, and the site still opens with no signal.
//
//   The page (index.html): the network first, so every visit gets the latest code; the saved
//     copy only when the network fails or takes more than 3 seconds.
//   Data (/data/*): the network first, always (odds and picks move); the last copy saved only
//     when there's no connection, so a visitor at a stadium with no signal still sees the
//     board as of its last update (the page shows when that was).
//   Logos, fonts, headshots, icons and js/*.js (versioned by file): saved on first use and
//     served from the phone after that, no download and no round trip.
//
// Not registered under automation (the lock job, the change check and the probes drive the
// page in a browser and must get the files they serve themselves).
// To turn it off for everyone: replace this file's contents with the KILL block below.
//   self.addEventListener("install", () => self.skipWaiting());
//   self.addEventListener("activate", (e) => e.waitUntil((async () => {
//     for (const k of await caches.keys()) await caches.delete(k);
//     await self.registration.unregister();
//     for (const c of await self.clients.matchAll()) c.navigate(c.url);
//   })()));
const ASSETS = "gg-assets-1", PAGES = "gg-pages-1", DATA = "gg-data-1";
const KEEP = [ASSETS, PAGES, DATA];

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (!KEEP.includes(k)) await caches.delete(k);
  await self.clients.claim();
})()));

const isAsset = (u) => /^\/(assets|js)\//.test(u.pathname) || /\.(woff2?|webp|png|jpe?g|svg|ico)$/.test(u.pathname) || u.pathname === "/manifest.webmanifest";
const isPage = (req, u) => req.mode === "navigate" && (u.pathname === "/" || u.pathname === "/index.html");
const isData = (u) => u.pathname.startsWith("/data/") && u.pathname.endsWith(".json");

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const u = new URL(req.url);
  if (u.origin !== self.location.origin) return;
  if (isPage(req, u)) e.respondWith(page(req));
  else if (isAsset(u)) e.respondWith(asset(req));
  else if (isData(u)) e.respondWith(data(req, u));
});

function timeout(ms) { return new Promise((_, no) => setTimeout(() => no(new Error("slow")), ms)); }

async function page(req) {
  const cache = await caches.open(PAGES);
  // a fresh request from the URL: a page request can't take extra options itself (the browser
  // rejects it, which would leave every visit on the saved copy)
  const net = fetch(new Request(req.url, { cache: "no-cache", credentials: "same-origin" })).then((res) => {
    if (res.ok) cache.put("/", res.clone());
    return res;
  });
  try {
    return await Promise.race([net, timeout(3000)]);
  } catch (e) {
    const saved = await cache.match("/");
    if (saved) return saved;
    return net;   // nothing saved: wait for the network however long it takes
  }
}

async function asset(req) {
  const cache = await caches.open(ASSETS);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok && res.type === "basic") {
    await cache.put(req, res.clone());
    // a new version of a file (?v=) replaces the old one instead of piling up on the phone
    const u = new URL(req.url);
    if (u.search) for (const k of await cache.keys()) { const o = new URL(k.url); if (o.pathname === u.pathname && o.search !== u.search) cache.delete(k); }
  }
  return res;
}

async function data(req, u) {
  const cache = await caches.open(DATA);
  const key = u.origin + u.pathname;   // the ?t= that busts the browser cache isn't part of the key
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(key, res.clone());
    return res;
  } catch (e) {
    const saved = await cache.match(key);
    if (saved) return saved;
    throw e;
  }
}
