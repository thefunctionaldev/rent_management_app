// The apps as installable phone apps: service worker, install prompt, offline state and
// phone notifications. The server side is rent_management/pwa.py.
import { reactive } from "vue";

import { get, post } from "@/api";

export const pwa = reactive({
	app: null, // "rent" or "tenant"
	online: navigator.onLine,
	installPrompt: null, // Android / desktop Chrome: the browser's own install dialog
	installed: window.matchMedia?.("(display-mode: standalone)").matches || !!navigator.standalone,
	push: "unknown", // unsupported, blocked, off, on
});

const ua = navigator.userAgent;
// iPadOS says it's a Mac, but has a touch screen
export const isIOS =
	/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
export const isAndroid = /android/i.test(ua);
export const isPhone = isIOS || isAndroid;
// the browsers inside WhatsApp, Instagram, Facebook... can't add to the home screen
export const inAppBrowser = /FBAN|FBAV|Instagram|Line\/|WhatsApp|Snapchat|; wv\)/i.test(ua);
// on iPhone, Safari has the Share button at the bottom; other iOS browsers at the top
export const iosSafari = isIOS && !/CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua);

export function setupPwa(app) {
	pwa.app = app;
	window.addEventListener("online", () => (pwa.online = true));
	window.addEventListener("offline", () => (pwa.online = false));
	window.addEventListener("beforeinstallprompt", (event) => {
		event.preventDefault(); // shown from our own button instead
		pwa.installPrompt = event;
	});
	window.addEventListener("appinstalled", () => {
		pwa.installed = true;
		pwa.installPrompt = null;
	});
	// only when served by Frappe (not under `yarn dev`)
	if ("serviceWorker" in navigator && window.location.pathname.startsWith(`/${app}`)) {
		navigator.serviceWorker
			.register(`/${app}/sw.js`, { scope: `/${app}/` })
			.then(refreshPushState)
			.catch(() => (pwa.push = "unsupported"));
	} else {
		pwa.push = "unsupported";
	}
}

export async function install() {
	if (!pwa.installPrompt) return false;
	pwa.installPrompt.prompt();
	const { outcome } = await pwa.installPrompt.userChoice;
	pwa.installPrompt = null;
	return outcome === "accepted";
}

// what was loaded last is kept on the phone: remove it when logging out
export async function forgetOfflineData() {
	try {
		const subscription = await currentSubscription();
		if (subscription) {
			await post("rent_management.pwa.unsubscribe", { endpoint: subscription.endpoint });
			await subscription.unsubscribe();
		}
	} catch {
		// logged out anyway
	}
	if (window.caches) for (const key of await caches.keys()) await caches.delete(key);
}

// ---------------------------------------------------------------- phone notifications

async function currentSubscription() {
	if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;
	const registration = await navigator.serviceWorker.getRegistration(`/${pwa.app}/`);
	return registration ? registration.pushManager.getSubscription() : null;
}

export async function refreshPushState() {
	if (!("PushManager" in window) || !("Notification" in window))
		return (pwa.push = "unsupported");
	if (Notification.permission === "denied") return (pwa.push = "blocked");
	pwa.push = (await currentSubscription()) ? "on" : "off";
}

function keyBytes(base64) {
	const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
		.replace(/-/g, "+")
		.replace(/_/g, "/");
	return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

function deviceName() {
	const ua = navigator.userAgent;
	const os = /android/i.test(ua)
		? "Android"
		: isIOS
		? "iPhone"
		: /mac/i.test(ua)
		? "Mac"
		: /windows/i.test(ua)
		? "Windows"
		: "Computer";
	const browser = /edg\//i.test(ua)
		? "Edge"
		: /chrome|crios/i.test(ua)
		? "Chrome"
		: /firefox|fxios/i.test(ua)
		? "Firefox"
		: /safari/i.test(ua)
		? "Safari"
		: "browser";
	return `${os} · ${browser}`;
}

export async function enablePush() {
	if ((await Notification.requestPermission()) !== "granted") {
		await refreshPushState();
		throw new Error("Notifications are blocked. Allow them in the browser's site settings.");
	}
	const registration = await navigator.serviceWorker.ready;
	const key = await get("rent_management.pwa.push_key");
	const subscription =
		(await registration.pushManager.getSubscription()) ||
		(await registration.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey: keyBytes(key),
		}));
	await post("rent_management.pwa.subscribe", {
		endpoint: subscription.endpoint,
		app: pwa.app === "tenant" ? "Tenant" : "Manager",
		device: deviceName(),
	});
	pwa.push = "on";
}

export async function disablePush() {
	const subscription = await currentSubscription();
	if (subscription) {
		await post("rent_management.pwa.unsubscribe", { endpoint: subscription.endpoint });
		await subscription.unsubscribe();
	}
	pwa.push = "off";
}
