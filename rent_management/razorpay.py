# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Minimal Razorpay REST client for subscription payments.

Keys are read from the site / common site config (never from the database, so customers
can't see them):

    bench set-config -g razorpay_key_id rzp_live_xxx
    bench set-config -g razorpay_key_secret xxx
    bench set-config -g razorpay_webhook_secret xxx   # optional, for the webhook
"""

import hashlib
import hmac

import frappe
import requests
from frappe import _
from frappe.utils import flt

API_URL = "https://api.razorpay.com/v1"
TIMEOUT = 20


def get_key_id() -> str:
	return frappe.conf.get("razorpay_key_id") or ""


def get_key_secret() -> str:
	return frappe.conf.get("razorpay_key_secret") or ""


def is_configured() -> bool:
	return bool(get_key_id() and get_key_secret())


def to_subunits(amount) -> int:
	"""Razorpay amounts are in paise (or the currency's smallest unit)."""
	return round(flt(amount) * 100)


def request(method: str, path: str, data=None, params=None) -> dict:
	if not is_configured():
		frappe.throw(_("Online payments are not set up yet. Please contact support to renew your plan."))
	try:
		response = requests.request(
			method,
			f"{API_URL}{path}",
			json=data,
			params=params,
			auth=(get_key_id(), get_key_secret()),
			timeout=TIMEOUT,
		)
	except requests.RequestException:
		frappe.log_error(title="Razorpay request failed")
		frappe.throw(_("Could not reach the payment gateway. Please try again in a minute."))

	body = response.json() if response.content else {}
	if not response.ok:
		frappe.log_error(title=f"Razorpay {method} {path} failed", message=frappe.as_json(body))
		description = (body.get("error") or {}).get("description") or response.reason
		frappe.throw(_("Payment gateway error: {0}").format(description))
	return body


def create_order(amount, currency: str, receipt: str, notes=None) -> dict:
	return request(
		"POST",
		"/orders",
		{"amount": to_subunits(amount), "currency": currency, "receipt": receipt, "notes": notes or {}},
	)


def get_payment(payment_id: str) -> dict:
	return request("GET", f"/payments/{payment_id}")


def capture_payment(payment_id: str, amount: int, currency: str) -> dict:
	return request("POST", f"/payments/{payment_id}/capture", {"amount": amount, "currency": currency})


def get_order_payments(order_id: str) -> list[dict]:
	return request("GET", f"/orders/{order_id}/payments").get("items", [])


def signature_matches(message: bytes, signature: str, secret: str) -> bool:
	if not (secret and signature):
		return False
	expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
	"""Signature Razorpay Checkout returns to the browser: HMAC(order_id|payment_id, key secret)."""
	return signature_matches(f"{order_id}|{payment_id}".encode(), signature, get_key_secret())


def verify_webhook_signature(body: bytes, signature: str) -> bool:
	return signature_matches(body, signature, frappe.conf.get("razorpay_webhook_secret") or "")
