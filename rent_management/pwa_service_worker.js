// Service worker of the /__APP__/ app, served at /__APP__/sw.js by rent_management/pwa.py.
// - the app opens without a signal: the page and its files come from the cache
// - pages show the last data they loaded (API reads are network first, then the cache)
// - phone notifications: a push carries no data, so we ask the site what's new

const APP = "__APP__";
const CACHE = `${APP}-__VERSION__`;
const SHELL = `/${APP}/`;
const NO_CACHE = ["rent_management.pwa.pending", "logout", "login"];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) =>
				fetch(SHELL, { credentials: "same-origin" }).then(
					(response) => response.ok && !response.redirected && cache.put(SHELL, response)
				)
			)
			.catch(() => {}) // offline or logged out: cached on the next visit
			.then(() => self.skipWaiting())
	);
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((key) => key.startsWith(`${APP}-`) && key !== CACHE)
						.map((key) => caches.delete(key))
				)
			)
			.then(() => self.clients.claim())
	);
});

async function networkFirst(request, cacheKey = request) {
	const cache = await caches.open(CACHE);
	try {
		const response = await fetch(request);
		// a redirect to the login page isn't the app
		if (response.ok && !response.redirected) cache.put(cacheKey, response.clone());
		return response;
	} catch (error) {
		const cached = await cache.match(cacheKey);
		if (cached) return cached;
		throw error;
	}
}

async function cacheFirst(request) {
	const cache = await caches.open(CACHE);
	const cached = await cache.match(request);
	if (cached) return cached;
	const response = await fetch(request);
	if (response.ok) cache.put(request, response.clone());
	return response;
}

self.addEventListener("fetch", (event) => {
	const { request } = event;
	const url = new URL(request.url);
	if (request.method !== "GET" || url.origin !== self.location.origin) return;

	if (request.mode === "navigate" && url.pathname.startsWith(SHELL)) {
		// every page of the app is the same page
		event.respondWith(networkFirst(request, SHELL));
	} else if (url.pathname.startsWith("/assets/")) {
		event.respondWith(cacheFirst(request));
	} else if (url.pathname.startsWith("/files/") || url.pathname.startsWith("/private/files/")) {
		// photos: a changed photo gets a new file name, so the cached copy is fine
		event.respondWith(cacheFirst(request));
	} else if (
		url.pathname.startsWith("/api/method/") &&
		!NO_CACHE.some((m) => url.pathname.includes(m))
	) {
		event.respondWith(networkFirst(request));
	}
});

// ---------------------------------------------------------------- notifications

self.addEventListener("push", (event) => {
	event.waitUntil(
		fetch("/api/method/rent_management.pwa.pending", { credentials: "same-origin" })
			.then((response) => response.json())
			.then((data) => data.message || [])
			.catch(() => [])
			.then((items) => {
				if (!items.length)
					items = [
						{
							id: "new",
							title: "Rent Management",
							body: "There's something new for you.",
							url: SHELL,
						},
					];
				return Promise.all(
					items.map((item) =>
						self.registration.showNotification(item.title, {
							body: item.body,
							tag: item.id, // the same notification never shows twice
							icon: "/assets/rent_management/icons/icon-192.png",
							badge: "/assets/rent_management/icons/icon-192.png",
							data: { url: item.url || SHELL },
						})
					)
				);
			})
	);
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const url = new URL(event.notification.data?.url || SHELL, self.location.origin).href;
	event.waitUntil(
		self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
			const open = windows.find((w) => w.url.includes(SHELL));
			if (open) return open.navigate(url).then((w) => (w || open).focus());
			return self.clients.openWindow(url);
		})
	);
});
