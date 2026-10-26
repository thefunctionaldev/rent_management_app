# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Running the SaaS: your control site.

One site on the bench is your own "control site" (`rent_control_site: 1` in its
site_config.json, and `rent_subscription_enabled: 0` so it isn't billed itself). It

- receives a signed daily heartbeat from every customer site, so you can see all customers,
  trials, renewals and revenue in one place (SaaS Customer, /rent/saas);
- hosts the public signup page that creates new customer sites (signup.py);
- receives Razorpay webhooks for all sites and forwards each one to its site.

Every customer site needs, in common_site_config.json:

    "rent_control_url": "https://admin.yourdomain.com",
    "rent_control_secret": "<long random string>"
"""

import hashlib
import hmac
import json
import re
from collections import defaultdict

import frappe
import requests
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, get_first_day, getdate, now_datetime, nowdate

from rent_management import subscription

CUSTOMER = "SaaS Customer"
SIGNATURE_HEADER = "X-Rent-Signature"
SITE_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,253}[a-z0-9])?$")


def is_control_site() -> bool:
	return bool(cint(frappe.conf.get("rent_control_site")))


def only_control_site():
	if not is_control_site():
		frappe.throw(_("This only works on the control site."), frappe.PermissionError)


def sign(body: bytes) -> str:
	secret = frappe.conf.get("rent_control_secret") or ""
	return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def signature_valid(body: bytes, signature: str) -> bool:
	return bool(frappe.conf.get("rent_control_secret") and signature) and hmac.compare_digest(
		sign(body), signature
	)


# ---------------------------------------------------------------- customer site: heartbeat


def build_heartbeat() -> dict:
	state = subscription.get_state()
	sub = frappe.get_single(subscription.SUBSCRIPTION)
	paid = frappe.get_all(
		subscription.PAYMENT,
		filters={"status": "Paid", "amount": (">", 0)},
		fields=["amount", "paid_on"],
		order_by="paid_on asc",
	)
	managers = subscription.get_manager_users()
	return {
		"site": frappe.local.site,
		"status": state["status"],
		"plan": state["plan"],
		"billing_cycle": state["billing_cycle"],
		"auto_renew": cint(sub.get("auto_renew")),
		"trial_ends_on": str(sub.trial_ends_on or "") or None,
		"current_period_end": str(sub.current_period_end or "") or None,
		"total_paid": sum(flt(p.amount) for p in paid),
		"first_paid_on": str(getdate(paid[0].paid_on)) if paid else None,
		"last_payment_on": str(getdate(paid[-1].paid_on)) if paid else None,
		"billing_name": sub.billing_name,
		"contact_email": sub.billing_email or (managers[0] if managers else None),
		"contact_phone": frappe.db.get_single_value("Rent Management Settings", "landlord_phone"),
		"tenants": frappe.db.count("Tenant Space Allotment", {"docstatus": 1, "status": "Active"}),
		**state["usage"],
		"sent_at": str(now_datetime()),
	}


def send_heartbeat():
	"""Scheduler (daily) and after payments: tell the control site how this site is doing."""
	url = frappe.conf.get("rent_control_url")
	if not url or not frappe.conf.get("rent_control_secret") or is_control_site():
		return
	body = json.dumps(build_heartbeat(), default=str).encode()
	try:
		response = requests.post(
			f"{url.rstrip('/')}/api/method/rent_management.saas.heartbeat",
			data=body,
			headers={"Content-Type": "application/json", SIGNATURE_HEADER: sign(body)},
			timeout=15,
		)
		response.raise_for_status()
	except requests.RequestException:
		frappe.log_error(title="Heartbeat to the control site failed")


# ---------------------------------------------------------------- control site: receive


@frappe.whitelist(allow_guest=True, methods=["POST"])
def heartbeat():
	only_control_site()
	body = frappe.request.get_data()
	if not signature_valid(body, frappe.get_request_header(SIGNATURE_HEADER) or ""):
		frappe.throw(_("Invalid signature"), frappe.AuthenticationError)
	record_heartbeat(json.loads(body))
	return {"status": "ok"}


def record_heartbeat(data: dict):
	site = str(data.get("site") or "").lower()
	if not SITE_PATTERN.match(site):
		frappe.throw(_("Invalid site"))
	values = {
		field: data.get(field)
		for field in (
			"status",
			"plan",
			"billing_cycle",
			"auto_renew",
			"trial_ends_on",
			"current_period_end",
			"total_paid",
			"first_paid_on",
			"last_payment_on",
			"beds",
			"rooms",
			"properties",
			"users",
			"tenants",
		)
	}
	if values["status"] not in ("Trial", "Active", "Past Due", "Expired"):
		values["status"] = "Unknown"
	values["mrr"] = monthly_revenue(values["status"], values["plan"], values["billing_cycle"])
	values["last_seen"] = now_datetime()
	for field in ("billing_name", "contact_email", "contact_phone"):
		if data.get(field):
			values[field] = data[field]

	if frappe.db.exists(CUSTOMER, site):
		doc = frappe.get_doc(CUSTOMER, site)
		doc.update(values)
	else:
		doc = frappe.get_doc({"doctype": CUSTOMER, "site": site, **values})
		doc.signup = frappe.db.get_value("SaaS Signup", {"site": site})
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


def monthly_revenue(status, plan, billing_cycle) -> float:
	if status not in ("Active", "Past Due") or billing_cycle not in subscription.CYCLES:
		return 0
	plan_doc = subscription.get_plans().get(plan) or {}
	price = flt(plan_doc.get(billing_cycle.lower()))
	return flt(price / subscription.CYCLES[billing_cycle], 2)


# ---------------------------------------------------------------- control site: dashboard


@frappe.whitelist()
def get_dashboard():
	only_control_site()
	frappe.only_for("System Manager")
	today = getdate(nowdate())
	customers = frappe.get_all(
		CUSTOMER,
		fields=[
			"site",
			"billing_name",
			"contact_email",
			"contact_phone",
			"status",
			"plan",
			"billing_cycle",
			"auto_renew",
			"mrr",
			"trial_ends_on",
			"current_period_end",
			"first_paid_on",
			"last_payment_on",
			"total_paid",
			"last_seen",
			"beds",
			"tenants",
			"creation",
		],
		order_by="creation desc",
	)
	by_status = defaultdict(int)
	for c in customers:
		by_status[c.status] += 1

	def due_within(date, days):
		return date and today <= getdate(date) <= add_days(today, days)

	trials_ended = [c for c in customers if c.trial_ends_on and getdate(c.trial_ends_on) < today]
	converted = [c for c in trials_ended if c.first_paid_on]
	mrr = sum(flt(c.mrr) for c in customers)
	months = [get_first_day(add_months(today, -i)) for i in range(5, -1, -1)]
	return {
		"mrr": mrr,
		"arr": mrr * 12,
		"by_status": dict(by_status),
		"customers": len(customers),
		"paying": sum(1 for c in customers if c.status in ("Active", "Past Due")),
		"conversion": round(len(converted) / len(trials_ended) * 100) if trials_ended else None,
		"revenue_total": sum(flt(c.total_paid) for c in customers),
		"trials_ending": [c for c in customers if c.status == "Trial" and due_within(c.trial_ends_on, 7)],
		"renewals_due": [
			c
			for c in customers
			if c.status == "Active" and not c.auto_renew and due_within(c.current_period_end, 7)
		],
		"past_due": [c for c in customers if c.status == "Past Due"],
		"silent": [
			c for c in customers if c.last_seen and getdate(c.last_seen) < add_days(today, -2)
		],  # no heartbeat for 2 days: site down?
		"signups": [
			{
				"month": m.strftime("%b"),
				"count": sum(1 for c in customers if get_first_day(getdate(c.creation)) == m),
			}
			for m in months
		],
		"pending_signups": frappe.db.count(
			"SaaS Signup", {"status": ("in", ("Verified", "Provisioning", "Failed"))}
		),
		"list": customers,
	}


# ---------------------------------------------------------------- control site: Razorpay webhooks


def find_site(event: dict) -> str | None:
	"""The customer site an event belongs to: every order and subscription we create carries
	notes.site."""
	for entity in ("subscription", "order", "payment", "invoice"):
		notes = ((event.get("payload") or {}).get(entity) or {}).get("entity", {}).get("notes") or {}
		if isinstance(notes, dict) and notes.get("site"):
			return str(notes["site"]).lower()
	return None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""The webhook URL of your Razorpay account (subscriptions and orders of all customer sites).

	Razorpay sends every event to one URL, so the control site checks the signature and passes
	the event on, unchanged and with its signature, to the site it belongs to."""
	only_control_site()
	from rent_management import razorpay

	body = frappe.request.get_data()
	signature = frappe.get_request_header("X-Razorpay-Signature") or ""
	if not razorpay.verify_webhook_signature(body, signature):
		frappe.throw(_("Invalid signature"), frappe.AuthenticationError)

	site = find_site(json.loads(body or b"{}"))
	if not site or site == frappe.local.site or not frappe.db.exists(CUSTOMER, site):
		return {"status": "ignored"}

	path = "/api/method/rent_management.subscription.razorpay_webhook"
	headers = {"Content-Type": "application/json", "X-Razorpay-Signature": signature}
	base = frappe.conf.get("rent_webhook_forward_base")  # e.g. http://127.0.0.1:8000 on the same server
	if base:
		url, headers["Host"] = f"{base.rstrip('/')}{path}", site
	else:
		url = f"{frappe.conf.get('rent_signup_scheme') or 'https'}://{site}{path}"
	response = requests.post(url, data=body, headers=headers, timeout=15)
	if not response.ok:
		# a failed response makes Razorpay retry the webhook later
		frappe.throw(_("Forwarding to {0} failed ({1})").format(site, response.status_code))
	return {"status": "forwarded", "site": site}
