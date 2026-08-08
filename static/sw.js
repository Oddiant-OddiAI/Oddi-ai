const CACHE_NAME = "vedAura-v2";

const FILES_TO_CACHE = [
    "/static/style.css",
    "/static/mobile.css",
    "/static/favicon2.png",
    "/static/logo.png",
    "/static/manifest.json"
];

// Install
self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(FILES_TO_CACHE))
            .then(() => self.skipWaiting())
    );
});

// Activate
self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

// Fetch
self.addEventListener("fetch", event => {

    // Only handle GET requests
    if (event.request.method !== "GET") {
        return;
    }

    // Network first
    event.respondWith(
        fetch(event.request)
            .catch(() => caches.match(event.request))
    );
});