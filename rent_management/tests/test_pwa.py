# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import pwa

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


def b64decode(value):
	return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TestPwa(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(pwa.SUBSCRIPTION)

	def tearDown(self):
		frappe.set_user("Administrator")

	def render(self, path):
		with patch.object(frappe.local, "request", SimpleNamespace(path=path), create=True):
			renderer = pwa.AppFilesRenderer("rent")
			return renderer.render() if renderer.can_render() else None

	def test_manifest_and_service_worker(self):
		manifest = json.loads(self.render("/rent/manifest.webmanifest").get_data())
		self.assertEqual(
			(manifest["scope"], manifest["start_url"], manifest["display"]),
			("/rent/", "/rent/", "standalone"),
		)
		self.assertIn("/rent/payments?new=1", [s["url"] for s in manifest["shortcuts"]])
		self.assertIn("maskable", [i.get("purpose") for i in manifest["icons"]])

		response = self.render("/rent/sw.js")
		self.assertEqual(response.mimetype, "application/javascript")
		self.assertEqual(response.headers["Service-Worker-Allowed"], "/rent/")
		source = response.get_data(as_text=True)
		self.assertIn('const APP = "rent";', source)
		self.assertNotIn("__VERSION__", source)
		self.assertIn('const APP = "tenant";', self.render("/tenant/sw.js").get_data(as_text=True))
		self.assertIsNone(self.render("/rent/rooms"))  # the app itself

	def test_vapid_keys_and_token(self):
		from cryptography.hazmat.primitives import hashes
		from cryptography.hazmat.primitives.asymmetric import ec
		from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

		public, private = pwa.keys()
		self.assertEqual(pwa.keys()[0], public)  # made once, then kept
		self.assertEqual(len(b64decode(public)), 65)  # an uncompressed P-256 point

		token = pwa.vapid_token(ENDPOINT, private)
		header, claims, signature = token.split(".")
		self.assertEqual(json.loads(b64decode(claims))["aud"], "https://fcm.googleapis.com")
		raw = b64decode(signature)
		key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64decode(public))
		key.verify(  # raises if the signature is wrong
			encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
			f"{header}.{claims}".encode(),
			ec.ECDSA(hashes.SHA256()),
		)

	def test_subscribe_and_pending(self):
		pwa.subscribe(ENDPOINT, "Manager", "Android · Chrome")
		pwa.subscribe(ENDPOINT, "Manager", "Android · Chrome")  # again: the same one
		self.assertEqual(frappe.db.count(pwa.SUBSCRIPTION, {"user": "Administrator"}), 1)
		self.assertRaises(frappe.ValidationError, pwa.subscribe, "http://insecure.example/x")

		with patch.object(frappe, "enqueue") as enqueue:
			from rent_management.portal import notify_managers

			with patch("rent_management.subscription.get_manager_users", return_value=["Administrator"]):
				notify_managers("Asha asked for leave", "Room 101, 3 nights", link="/rent/register?tab=leave")
		enqueue.assert_called()
		self.assertEqual(enqueue.call_args.kwargs["user"], "Administrator")
		latest = pwa.pending()[0]
		self.assertEqual(
			(latest["title"], latest["url"]), ("Asha asked for leave", "/rent/register?tab=leave")
		)

		pwa.unsubscribe(ENDPOINT)
		self.assertFalse(frappe.db.exists(pwa.SUBSCRIPTION, {"user": "Administrator"}))

	def test_send_push(self):
		pwa.subscribe(ENDPOINT, "Manager")
		pwa.subscribe(ENDPOINT + "-gone", "Manager")
		calls = []

		def post(url, headers, timeout):
			calls.append((url, headers))
			return SimpleNamespace(
				status_code=410 if url.endswith("-gone") else 201, ok=not url.endswith("-gone")
			)

		with patch.object(pwa.requests, "post", post):
			self.assertEqual(pwa.send_push("Administrator"), 1)
		self.assertTrue(calls[0][1]["Authorization"].startswith("vapid t="))
		self.assertIn(f"k={pwa.keys()[0]}", calls[0][1]["Authorization"])
		self.assertEqual(frappe.db.count(pwa.SUBSCRIPTION), 1)  # the unsubscribed phone is forgotten
		self.assertTrue(frappe.db.get_value(pwa.SUBSCRIPTION, {}, "last_sent"))
