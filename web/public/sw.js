/*
 * Service Worker for Tog & Dogs Operations Portal
 *
 * NOTE: Caching, precaching, and offline support are intentionally disabled to
 * eliminate the risk of stale content in production. All requests are passed
 * directly through to the network.
 *
 * This file exists purely to satisfy PWA installability requirements for Chrome
 * and other mobile browsers to display the automatic installation banner.
 */

// Install event — skip waiting to activate immediately
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

// Activate event — claim clients immediately
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Fetch event — minimal no-op fetch handler to satisfy PWA criteria.
// Passes all requests straight through to the network without caching anything.
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
