# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The manager app (/rent) and the tenant app (/tenant) as installable phone apps.

- /rent/manifest.webmanifest and /tenant/manifest.webmanifest describe each app (name, icons,
  home-screen shortcuts), and /rent/sw.js and /tenant/sw.js are their service workers
  (pwa_service_worker.js). They're served under the app's path so the worker controls it.
- The service worker keeps the last data each page loaded, so the app still opens and shows it
  when the signal drops.
- Phone notifications: every app notification a manager gets (a Notification Log: new leads,
  leave requests, payments to confirm...) is also pushed to the phones they turned them on.
  The push carries no data; the phone asks this site what's new (pending()). That only needs a
  signed VAPID token, made with the site's own key pair, so no push library is needed.
"""

import base64
import hashlib
import json
import os
import time
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

SETTINGS = "Rent Management Settings"
SUBSCRIPTION = "Push Subscription"
ICONS = "/assets/rent_management/icons"
THEME = "#4f46e5"
APPS = {
	"rent": {
		"name": _("Rent Management"),
		"short_name": _("Rent"),
		"description": _("Rooms, tenants, rent and your buildings, on your phone."),
		"shortcuts": [
			(_("Record payment"), "/rent/payments?new=1"),
			(_("Night attendance"), "/rent/register"),
			(_("Visitor at the gate"), "/rent/register?tab=visitors&new=1"),
			(_("Add lead"), "/rent/leads?new=1"),
		],
	},
	"tenant": {
		"name": _("My Rent"),
		"short_name": _("My Rent"),
		"description": _("Your rent bills, payments and requests."),
		"shortcuts": [
			(_("Pay rent"), "/tenant/"),
			(_("Raise a request"), "/tenant/requests"),
		],
	},
}


# ---------------------------------------------------------------- manifest and service worker


def business_name() -> str:
	settings = frappe.get_cached_doc(SETTINGS)
	buildings = frappe.get_all("Rent Property", filters={"is_active": 1}, pluck="property_name", limit=2)
	return (
		(buildings[0] if len(buildings) == 1 else None) or settings.upi_payee_name or settings.landlord_name
	)


def manifest(app: str) -> dict:
	meta = APPS[app]
	business = business_name()
	return {
		"name": f"{meta['name']} · {business}" if business else meta["name"],
		"short_name": (business or meta["short_name"])[:12] if app == "tenant" else meta["short_name"],
		"description": meta["description"],
		"id": f"/{app}/",
		"start_url": f"/{app}/",
		"scope": f"/{app}/",
		"display": "standalone",
		"orientation": "portrait",
		"background_color": "#f8fafc",
		"theme_color": THEME,
		"icons": [
			{"src": f"{ICONS}/icon-192.png", "sizes": "192x192", "type": "image/png"},
			{"src": f"{ICONS}/icon-512.png", "sizes": "512x512", "type": "image/png"},
			{
				"src": f"{ICONS}/icon-maskable-512.png",
				"sizes": "512x512",
				"type": "image/png",
				"purpose": "maskable",
			},
		],
		"shortcuts": [
			{
				"name": name,
				"short_name": name,
				"url": url,
				"icons": [{"src": f"{ICONS}/icon-192.png", "sizes": "192x192"}],
			}
			for name, url in meta["shortcuts"]
		],
	}


def service_worker(app: str) -> str:
	path = os.path.join(os.path.dirname(__file__), "pwa_service_worker.js")
	with open(path) as f:
		source = f.read()
	# a new version of the app (or of this file) makes phones fetch everything again
	version = hashlib.sha1(
		(source + str(frappe.get_attr("rent_management.__version__"))).encode()
	).hexdigest()[:10]
	return source.replace("__APP__", app).replace("__VERSION__", version)


FILES = {f"{app}/{name}": (app, name) for app in APPS for name in ("manifest.webmanifest", "sw.js")}


class AppFilesRenderer(BaseRenderer):
	"""Serves the manifest and service worker of each app at the app's own path."""

	def can_render(self):
		return self.request_path() in FILES

	def request_path(self):
		return (frappe.local.request.path if getattr(frappe.local, "request", None) else self.path).strip("/")

	def render(self):
		app, name = FILES[self.request_path()]
		if name == "sw.js":
			body, mimetype = service_worker(app), "application/javascript"
			headers = {"Cache-Control": "no-cache", "Service-Worker-Allowed": f"/{app}/"}
		else:
			body, mimetype = json.dumps(manifest(app), ensure_ascii=False), "application/manifest+json"
			headers = {"Cache-Control": "no-cache"}
		return Response(body, mimetype=mimetype, headers=headers)


# ---------------------------------------------------------------- push: keys and tokens


def b64url(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def keys() -> tuple[str, object]:
	"""The site's VAPID key pair (made the first time): the public key for browsers, the private key."""
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import ec

	settings = frappe.get_single(SETTINGS)
	pem = (
		settings.get_password("vapid_private_key", raise_exception=False)
		if settings.vapid_public_key
		else None
	)
	if pem:
		private = serialization.load_pem_private_key(pem.encode(), password=None)
	else:
		private = ec.generate_private_key(ec.SECP256R1())
		pem = private.private_bytes(
			serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
		).decode()
		public = private.public_key().public_bytes(
			serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
		)
		settings.vapid_public_key = b64url(public)
		settings.vapid_private_key = pem
		settings.flags.ignore_permissions = True
		settings.save()
	return settings.vapid_public_key, private


def vapid_token(endpoint: str, private) -> str:
	"""A JWT (ES256) that says this site sends to the push service of the endpoint."""
	from cryptography.hazmat.primitives import hashes
	from cryptography.hazmat.primitives.asymmetric import ec
	from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

	url = urlparse(endpoint)
	header = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
	claims = b64url(
		json.dumps(
			{
				"aud": f"{url.scheme}://{url.netloc}",
				"exp": int(time.time()) + 12 * 3600,
				"sub": f"mailto:{frappe.conf.get('push_contact_email') or 'admin@' + (frappe.local.site or 'localhost')}",
			}
		).encode()
	)
	signing_input = f"{header}.{claims}".encode()
	r, s = decode_dss_signature(private.sign(signing_input, ec.ECDSA(hashes.SHA256())))
	signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
	return f"{header}.{claims}.{b64url(signature)}"


# ---------------------------------------------------------------- push: sending


def on_notification(doc, method=None):
	"""Notification Log after_insert: push it to the user's phones."""
	if doc.for_user and frappe.db.exists(SUBSCRIPTION, {"user": doc.for_user}):
		frappe.enqueue(
			"rent_management.pwa.send_push", user=doc.for_user, queue="short", enqueue_after_commit=True
		)


def send_push(user: str) -> int:
	"""Wake the user's phones: they fetch what's new themselves. Returns how many were reached."""
	public, private = keys()
	reached = 0
	for sub in frappe.get_all(SUBSCRIPTION, filters={"user": user}, fields=["name", "endpoint", "failures"]):
		try:
			response = requests.post(
				sub.endpoint,
				headers={
					"TTL": str(24 * 3600),
					"Urgency": "high",
					"Authorization": f"vapid t={vapid_token(sub.endpoint, private)}, k={public}",
				},
				timeout=10,
			)
		except requests.RequestException:
			response = None
		if response is not None and response.status_code in (404, 410):
			frappe.delete_doc(SUBSCRIPTION, sub.name, ignore_permissions=True)  # the phone unsubscribed
		elif response is not None and response.ok:
			frappe.db.set_value(SUBSCRIPTION, sub.name, {"last_sent": now_datetime(), "failures": 0})
			reached += 1
		elif cint(sub.failures) >= 9:
			frappe.delete_doc(SUBSCRIPTION, sub.name, ignore_permissions=True)
		else:
			frappe.db.set_value(SUBSCRIPTION, sub.name, "failures", cint(sub.failures) + 1)
	return reached


# ---------------------------------------------------------------- for the apps


@frappe.whitelist()
def push_key() -> str:
	return keys()[0]


@frappe.whitelist(methods=["POST"])
def subscribe(endpoint, app="Manager", device=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in first."), frappe.PermissionError)
	if not str(endpoint or "").startswith("https://"):
		frappe.throw(_("That isn't a push address."))
	existing = frappe.db.get_value(
		SUBSCRIPTION, {"endpoint_hash": hashlib.sha256(endpoint.encode()).hexdigest()}
	)
	doc = frappe.get_doc(SUBSCRIPTION, existing) if existing else frappe.new_doc(SUBSCRIPTION)
	doc.update(
		{
			"user": frappe.session.user,
			"endpoint": endpoint,
			"app": app if app in ("Manager", "Tenant") else "Manager",
			"device": (device or "")[:140],
			"failures": 0,
		}
	)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
	name = frappe.db.get_value(
		SUBSCRIPTION,
		{"endpoint_hash": hashlib.sha256(str(endpoint).encode()).hexdigest(), "user": frappe.session.user},
	)
	if name:
		frappe.delete_doc(SUBSCRIPTION, name, ignore_permissions=True)


@frappe.whitelist()
def pending() -> list[dict]:
	"""For the service worker after a push: the user's new notifications."""
	rows = frappe.get_all(
		"Notification Log",
		filters={
			"for_user": frappe.session.user,
			"read": 0,
			"creation": (">=", add_to_date(now_datetime(), hours=-1)),
		},
		fields=["name", "subject", "email_content", "link"],
		order_by="creation desc",
		limit=3,
	)
	return [
		{
			"id": row.name,
			"title": frappe.utils.strip_html(row.subject or "")[:120],
			"body": frappe.utils.strip_html(row.email_content or "")[:240],
			"url": row.link or "/rent/",
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def test_push():
	"""Settings > This phone: send a test notification to the user's phones."""
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": frappe.session.user,
			"type": "Alert",
			"subject": _("Notifications are on"),
			"email_content": _("You'll get new leads, leave requests and payments to confirm here."),
			"link": "/rent/",
		}
	).insert(ignore_permissions=True)
