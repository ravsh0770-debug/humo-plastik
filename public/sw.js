/* HUMO PLASTIK — service worker (oflayn ishlash va tez yuklanish) */
const VERSION = "humo-v9";
const CORE = [
  "/", "/index.html", "/css/style.css", "/css/app.css","/js/i18n.js", "/js/app.js", "/manifest.webmanifest",
  "/img/favicon.svg", "/img/icon-192.png", "/img/hero.jpg",
  "/img/mayka.jpg", "/img/logo-bag.jpg", "/img/fasovka.jpg", "/img/ziplock.jpg", "/img/doypack.jpg",
  "/img/musor.jpg", "/img/qop.jpg", "/img/plyonka.jpg",
  "/api/products",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const put = (req, res) => {
  if (res && res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
  return res;
};

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return; // buyurtmalar doim to'g'ridan-to'g'ri serverga
  const url = new URL(req.url);
  const fonts = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (url.origin !== location.origin && !fonts) return;

  // Sahifa va narxlar: avval internetdan (yangi bo'lsin), bo'lmasa keshdan
  if (req.mode === "navigate" || url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(req).then(r => put(req, r))
        .catch(() => caches.match(req).then(r => r || caches.match("/")))
    );
    return;
  }
  // Rasmlar, CSS, JS, shriftlar: keshdan darhol, fonda yangilanadi
  e.respondWith(
    caches.match(req).then(cached => {
      const net = fetch(req).then(r => put(req, r)).catch(() => cached);
      return cached || net;
    })
  );
});
