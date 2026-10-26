# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""SaaS subscription for a customer site.

Every customer gets their own site. The site starts on a free trial, then the customer
pays for a plan (monthly or yearly) through Razorpay from /rent/billing. When the paid
period ends there are a few grace days, after which the site becomes read-only: all data
stays visible, but nothing can be created, changed or deleted until the plan is renewed.

Plans, prices, trial length and grace days can be overridden for the whole bench in
common_site_config.json (see README), so prices can change without a code release.
"""

import re

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import add_days, add_months, cint, date_diff, flt, getdate, now_datetime, nowdate

from rent_management import gst, razorpay

SUBSCRIPTION = "Rent Subscription"
PAYMENT = "Rent Subscription Payment"
MANAGER_ROLE = "Rent Manager"
CYCLES = {"Monthly": 1, "Yearly": 12}  # months per billing cycle

# limits: 0 means unlimited. Beds are what PGs and hostels price by, so plans are sized by beds.
DEFAULT_PLANS = {
	"starter": {
		"title": "Starter",
		"description": "For a single PG or a small building.",
		"monthly": 499,
		"yearly": 4990,
		"max_beds": 30,
		"max_properties": 1,
		"max_users": 2,
		"whatsapp": 0,
		"profit_report": 0,
		"features": [
			"Up to 30 beds in 1 building",
			"2 manager logins",
			"Rent invoices, online rent collection",
			"Tenant app and email reminders",
		],
	},
	"growth": {
		"title": "Growth",
		"description": "For growing hostels and PGs.",
		"monthly": 1499,
		"yearly": 14990,
		"max_beds": 120,
		"max_properties": 3,
		"max_users": 5,
		"whatsapp": 1,
		"profit_report": 1,
		"features": [
			"Up to 120 beds in 3 buildings",
			"5 manager logins",
			"Automatic WhatsApp reminders and receipts",
			"Expenses and profit report",
		],
	},
	"pro": {
		"title": "Pro",
		"description": "For large properties and multiple buildings.",
		"monthly": 3999,
		"yearly": 39990,
		"max_beds": 0,
		"max_properties": 0,
		"max_users": 0,
		"whatsapp": 1,
		"profit_report": 1,
		"features": [
			"Unlimited beds and buildings",
			"Unlimited manager logins",
			"Everything in Growth",
			"Priority support",
		],
	},
}

# usage key -> (plan limit key, label used in messages)
LIMITS = {
	"beds": ("max_beds", "beds"),
	"properties": ("max_properties", "buildings"),
	"users": ("max_users", "Rent Manager users"),
}


class SubscriptionExpiredError(frappe.ValidationError):
	pass


class PlanLimitError(frappe.ValidationError):
	pass


# ---------------------------------------------------------------- config


def get_plans() -> dict:
	return frappe.conf.get("rent_subscription_plans") or DEFAULT_PLANS


def get_plan(plan: str) -> dict:
	plans = get_plans()
	if plan not in plans:
		frappe.throw(_("Unknown plan {0}.").format(plan))
	return plans[plan]


def get_price(plan: str, billing_cycle: str) -> float:
	if billing_cycle not in CYCLES:
		frappe.throw(_("Billing cycle must be Monthly or Yearly."))
	return flt(get_plan(plan)[billing_cycle.lower()])


def get_currency() -> str:
	return frappe.conf.get("rent_subscription_currency") or "INR"


def trial_plan() -> str:
	return frappe.conf.get("rent_trial_plan") or "growth"


def trial_days() -> int:
	return cint(frappe.conf.get("rent_trial_days") or 14)


def grace_days() -> int:
	return cint(frappe.conf.get("rent_grace_days") or 3)


def is_enforced() -> bool:
	"""Subscriptions can be switched off for a site (e.g. your own demo site) with
	`bench --site <site> set-config rent_subscription_enabled 0`."""
	if frappe.flags.in_test:
		return bool(frappe.flags.enforce_rent_subscription)
	return bool(cint(frappe.conf.get("rent_subscription_enabled", 1)))


# ---------------------------------------------------------------- state


def get_status(sub, today=None) -> str:
	"""Trial / Active / Past Due (in grace period, still usable) / Expired."""
	today = getdate(today or nowdate())
	if sub.current_period_end:
		end = getdate(sub.current_period_end)
		if today <= end:
			return "Active"
		if today <= add_days(end, grace_days()):
			return "Past Due"
		return "Expired"
	if sub.trial_ends_on and today <= getdate(sub.trial_ends_on):
		return "Trial"
	return "Expired"


def is_usable(status: str) -> bool:
	return status in ("Trial", "Active", "Past Due")


def get_usage() -> dict:
	return {
		"beds": get_total_beds(),
		"rooms": frappe.db.count("Tenant Space"),
		"properties": frappe.db.count("Rent Property", {"is_active": 1}),
		"users": len(get_manager_users()),
	}


def get_total_beds(exclude_room=None) -> int:
	beds = frappe.get_all("Tenant Space", filters={"name": ("!=", exclude_room or "")}, pluck="capacity")
	return sum(max(cint(b), 1) for b in beds)


def get_manager_users(exclude=None) -> list[str]:
	"""Enabled users with the Rent Manager role. Administrator never counts."""
	users = frappe.get_all(
		"Has Role",
		filters={"role": MANAGER_ROLE, "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	enabled = frappe.get_all("User", filters={"name": ("in", users or [""]), "enabled": 1}, pluck="name")
	return [user for user in enabled if user not in ("Administrator", "Guest", exclude)]


def get_state() -> dict:
	"""Everything the frontend needs to show the subscription and billing page."""
	sub = frappe.get_single(SUBSCRIPTION)
	status = get_status(sub)
	plan_key = sub.plan or trial_plan()
	plan = get_plans().get(plan_key) or {}
	ends_on = sub.current_period_end or sub.trial_ends_on

	return {
		"enforced": is_enforced(),
		"status": status,
		"is_usable": is_usable(status),
		"plan": plan_key,
		"plan_title": plan.get("title", plan_key),
		"billing_cycle": sub.billing_cycle,
		"trial_ends_on": sub.trial_ends_on,
		"current_period_start": sub.current_period_start,
		"current_period_end": sub.current_period_end,
		"ends_on": ends_on,
		"days_left": date_diff(ends_on, nowdate()) if ends_on else 0,
		"grace_ends_on": add_days(sub.current_period_end, grace_days()) if sub.current_period_end else None,
		"limits": {key: cint(plan.get(limit)) for key, (limit, _label) in LIMITS.items()},
		"features": {
			"whatsapp": bool(cint(plan.get("whatsapp"))),
			"profit_report": bool(cint(plan.get("profit_report"))),
		},
		"usage": get_usage(),
		"currency": get_currency(),
	}


def update_subscription(**values):
	sub = frappe.get_single(SUBSCRIPTION)
	sub.update(values)
	sub.status = get_status(sub)
	sub.flags.ignore_permissions = True
	frappe.flags.updating_rent_subscription = True
	try:
		sub.save()
	finally:
		frappe.flags.updating_rent_subscription = False
	return sub


def start_trial(force=False):
	sub = frappe.get_single(SUBSCRIPTION)
	if (sub.trial_ends_on or sub.current_period_end) and not force:
		return
	update_subscription(
		plan=trial_plan(),
		billing_cycle=None,
		trial_ends_on=add_days(nowdate(), trial_days()),
		current_period_start=None,
		current_period_end=None,
	)


def after_install():
	from rent_management.onboarding import extend_invite_links
	from rent_management.patches.v1_4 import set_settings_defaults
	from rent_management.portal import ensure_tenant_role
	from rent_management.rent_management_system.doctype.rent_property.rent_property import (
		get_default_property,
	)

	get_default_property()
	set_settings_defaults.execute()
	ensure_tenant_role()
	extend_invite_links()
	start_trial()


# ---------------------------------------------------------------- enforcement (doc_events)


def skip_enforcement() -> bool:
	flags = frappe.flags
	return (
		not is_enforced()
		or flags.in_install
		or flags.in_migrate
		or flags.in_patch
		or flags.in_fixtures
		or flags.recording_online_payment  # money already received; see rent_collection.py
		or frappe.session.user == "Administrator"
	)


def check_writable(doc=None, method=None):
	"""Block every change to app data once the subscription has lapsed."""
	if skip_enforcement():
		return
	status = get_status(frappe.get_single(SUBSCRIPTION))
	if is_usable(status):
		return
	frappe.throw(
		_(
			"Your Rent Management subscription has expired, so the app is read-only. "
			"Renew your plan from <a href='/rent/billing'>Subscription & Billing</a> to continue."
		),
		SubscriptionExpiredError,
		title=_("Subscription expired"),
	)


def get_current_plan() -> dict:
	sub = frappe.get_single(SUBSCRIPTION)
	return get_plans().get(sub.plan or trial_plan()) or {}


def get_limit(key: str) -> int:
	return cint(get_current_plan().get(LIMITS[key][0]))


def has_feature(feature: str) -> bool:
	"""Plan features such as WhatsApp messages. Always on where subscriptions aren't enforced."""
	return not is_enforced() or bool(cint(get_current_plan().get(feature)))


def limit_error(message, title):
	frappe.throw(
		_("{0} Upgrade from <a href='/rent/billing'>Subscription & Billing</a> to add more.").format(message),
		PlanLimitError,
		title=title,
	)


def check_bed_limit(doc, method=None):
	"""Runs on Tenant Space validate: total beds across rooms must fit the plan."""
	if skip_enforcement():
		return
	limit = get_limit("beds")
	if not limit:
		return
	before = doc.get_doc_before_save()
	if before and cint(before.capacity) >= cint(doc.capacity):
		return  # not adding beds
	if get_total_beds(exclude_room=doc.name) + max(cint(doc.capacity), 1) > limit:
		limit_error(_("Your plan allows up to {0} beds.").format(limit), _("Bed limit reached"))


def check_property_limit(doc, method=None):
	"""Runs on Rent Property validate: a new or re-activated building must fit the plan."""
	if skip_enforcement() or not doc.is_active:
		return
	before = doc.get_doc_before_save()
	if before and before.is_active:
		return
	limit = get_limit("properties")
	if limit and frappe.db.count("Rent Property", {"is_active": 1, "name": ("!=", doc.name)}) >= limit:
		limit_error(_("Your plan allows {0} building(s).").format(limit), _("Building limit reached"))


def check_user_limit(doc, method=None):
	"""Runs on User validate: a user who newly becomes an enabled Rent Manager must fit the plan."""
	if skip_enforcement() or doc.name in ("Administrator", "Guest"):
		return
	is_manager = doc.enabled and MANAGER_ROLE in [r.role for r in doc.get("roles", [])]
	if not is_manager:
		return
	before = doc.get_doc_before_save()
	if before and before.enabled and MANAGER_ROLE in [r.role for r in before.get("roles", [])]:
		return  # already counted

	limit = get_limit("users")
	if limit and len(get_manager_users(exclude=doc.name)) >= limit:
		frappe.throw(
			_(
				"Your plan allows up to {0} Rent Manager users. Disable another user or upgrade "
				"from <a href='/rent/billing'>Subscription & Billing</a>."
			).format(limit),
			PlanLimitError,
			title=_("User limit reached"),
		)


def check_plan_fits(plan: str):
	"""Refuse a downgrade to a plan that is smaller than what the customer already uses."""
	limits = get_plan(plan)
	usage = get_usage()
	for key, (limit_key, label) in LIMITS.items():
		limit = cint(limits.get(limit_key))
		if limit and usage[key] > limit:
			frappe.throw(
				_(
					"The {0} plan allows {1} {2}, but you have {3}. Remove some first or choose a bigger plan."
				).format(limits.get("title", plan), limit, _(label), usage[key]),
				PlanLimitError,
			)


# ---------------------------------------------------------------- periods


def period_end_for(start, billing_cycle: str):
	return add_days(add_months(start, CYCLES[billing_cycle]), -1)


def get_new_period(plan: str, billing_cycle: str, today=None) -> tuple:
	"""Work out the period a payment buys, as (start, end, bonus_days).

	- Renewing the same plan and cycle while it is still running adds a period after
	  the current one ends, so paying early never loses days.
	- Switching plan or cycle while a paid period is running starts the new plan today
	  and turns the unused value of the old plan into extra days on the new one.
	- Otherwise (trial, or lapsed) the new period starts today.
	"""
	today = getdate(today or nowdate())
	sub = frappe.get_single(SUBSCRIPTION)
	current_end = getdate(sub.current_period_end) if sub.current_period_end else None
	running = current_end and current_end >= today

	if running and sub.plan == plan and sub.billing_cycle == billing_cycle:
		start = add_days(current_end, 1)
		return start, period_end_for(start, billing_cycle), 0

	end = period_end_for(today, billing_cycle)
	bonus_days = 0
	if running and sub.plan in get_plans() and sub.billing_cycle in CYCLES:
		unused_days = date_diff(current_end, today)
		old_daily = get_price(sub.plan, sub.billing_cycle) / cycle_days(
			sub.current_period_start, sub.billing_cycle
		)
		new_daily = get_price(plan, billing_cycle) / (date_diff(end, today) + 1)
		if new_daily > 0:
			bonus_days = int(unused_days * old_daily / new_daily)
	return today, add_days(end, bonus_days), bonus_days


def cycle_days(start, billing_cycle: str) -> int:
	start = getdate(start or nowdate())
	return date_diff(period_end_for(start, billing_cycle), start) + 1


# ---------------------------------------------------------------- checkout


def create_checkout(plan: str, billing_cycle: str) -> dict:
	"""Create a Razorpay order for a plan and return the options for Razorpay Checkout."""
	amount = gst.payable_amount(get_price(plan, billing_cycle))
	check_plan_fits(plan)
	if amount <= 0:
		frappe.throw(_("This plan has no price set."))

	payment = frappe.get_doc(
		{
			"doctype": PAYMENT,
			"plan": plan,
			"plan_title": get_plan(plan).get("title", plan),
			"billing_cycle": billing_cycle,
			"amount": amount,
			"currency": get_currency(),
			"payment_method": "Razorpay",
			"status": "Created",
			"paid_by": frappe.session.user,
		}
	)
	payment.flags.ignore_permissions = True
	payment.insert()

	order = razorpay.create_order(
		amount,
		payment.currency,
		receipt=payment.name,
		notes={"site": frappe.local.site, "plan": plan, "billing_cycle": billing_cycle},
	)
	payment.db_set("razorpay_order_id", order["id"])

	user = frappe.get_cached_doc("User", frappe.session.user)
	return {
		"key": razorpay.get_key_id(),
		"order_id": order["id"],
		"amount": order["amount"],
		"currency": order["currency"],
		"name": frappe.conf.get("rent_subscription_brand") or "Rent Management",
		"description": _("{0} plan, billed {1}").format(payment.plan_title, billing_cycle.lower()),
		"prefill": {"name": user.full_name, "email": user.email},
		"notes": {"site": frappe.local.site},
		"payment": payment.name,
	}


def verify_checkout(order_id: str, payment_id: str, signature: str) -> dict:
	"""Called by the browser after Razorpay Checkout succeeds."""
	if not razorpay.verify_payment_signature(order_id, payment_id, signature):
		frappe.throw(_("Payment could not be verified. If money was deducted, contact support."))
	return fulfil_order(order_id, payment_id)


def fulfil_order(order_id: str, payment_id: str) -> dict:
	"""Mark the subscription payment as paid and extend the subscription. Idempotent, so it is
	safe to run from the checkout callback, the webhook and the reconcile job for the same order."""
	name = frappe.db.get_value(PAYMENT, {"razorpay_order_id": order_id})
	if not name:
		frappe.throw(_("Unknown order {0}.").format(order_id))

	payment = frappe.get_doc(PAYMENT, name, for_update=True)
	if payment.status == "Paid":
		return get_state()

	rp_payment = razorpay.get_payment(payment_id)
	if rp_payment.get("order_id") != order_id:
		frappe.throw(_("Payment {0} does not belong to order {1}.").format(payment_id, order_id))
	if rp_payment.get("status") == "authorized":
		rp_payment = razorpay.capture_payment(payment_id, rp_payment["amount"], rp_payment["currency"])
	if rp_payment.get("status") != "captured":
		frappe.throw(_("Payment {0} is {1}, not captured.").format(payment_id, rp_payment.get("status")))
	if cint(rp_payment.get("amount")) != razorpay.to_subunits(payment.amount) or (
		rp_payment.get("currency") != payment.currency
	):
		frappe.throw(_("Payment amount does not match order {0}.").format(order_id))

	apply_payment(payment, payment_id=payment_id)
	return get_state()


def apply_payment(payment, payment_id=None, start=None, end=None):
	"""Extend the subscription by the period a payment buys and mark the payment paid."""
	if start and end:
		bonus_days = 0
	else:
		start, end, bonus_days = get_new_period(payment.plan, payment.billing_cycle)

	payment.update(
		{
			"status": "Paid",
			"razorpay_payment_id": payment_id or payment.razorpay_payment_id,
			"period_start": start,
			"period_end": end,
			"bonus_days": bonus_days,
			"paid_on": now_datetime(),
		}
	)
	if flt(payment.amount) > 0:
		set_tax_invoice(payment)
	payment.flags.ignore_permissions = True
	frappe.flags.updating_rent_subscription = True
	try:
		payment.save()
	finally:
		frappe.flags.updating_rent_subscription = False
	if payment.invoice_number:
		frappe.enqueue(email_invoice, payment=payment.name, enqueue_after_commit=True)
	if not frappe.flags.in_test:
		frappe.enqueue("rent_management.saas.send_heartbeat", enqueue_after_commit=True)

	sub = frappe.get_single(SUBSCRIPTION)
	update_subscription(
		plan=payment.plan,
		billing_cycle=payment.billing_cycle,
		current_period_start=start
		if getdate(start) <= getdate(nowdate())
		else sub.current_period_start or start,
		current_period_end=end,
	)
	return payment


# ---------------------------------------------------------------- tax invoices

INVOICE_PRINT_FORMAT = "Subscription Tax Invoice"


def invoice_prefix() -> str:
	"""Per-site invoice series, e.g. SHARMA/2627/0001. Invoice numbers must be unique for your
	GSTIN, so every customer site needs its own prefix (set at signup, or derived from the site)."""
	prefix = frappe.conf.get("rent_invoice_prefix") or re.sub(r"[^A-Za-z0-9]", "", frappe.local.site)[:6]
	return prefix.upper()[:6]


def financial_year(date) -> str:
	date = getdate(date)
	start = date.year if date.month >= 4 else date.year - 1
	return f"{start % 100:02d}{(start + 1) % 100:02d}"


def set_tax_invoice(payment):
	"""Give a paid subscription payment its invoice number and GST breakup."""
	if payment.invoice_number:
		return
	sub = frappe.get_single(SUBSCRIPTION)
	invoice_date = getdate(nowdate())
	payment.update(
		{
			"invoice_date": invoice_date,
			"billing_name": sub.billing_name or frappe.local.site,
			"billing_gstin": sub.billing_gstin,
			"billing_email": sub.billing_email,
			"billing_address": sub.billing_address,
			"billing_state": sub.billing_state,
			"place_of_supply": sub.billing_state or gst.get_vendor().state,
			**gst.get_breakup(payment.amount, sub.billing_state),
		}
	)
	payment.invoice_number = make_autoname(f"{invoice_prefix()}/{financial_year(invoice_date)}/.####")


def email_invoice(payment: str):
	payment = frappe.get_doc(PAYMENT, payment)
	recipients = [payment.billing_email] if payment.billing_email else get_manager_users()
	if not recipients:
		return
	try:
		attachments = [
			frappe.attach_print(
				PAYMENT,
				payment.name,
				print_format=INVOICE_PRINT_FORMAT,
				file_name=payment.invoice_number.replace("/", "-"),
			)
		]
	except Exception:
		frappe.log_error(title=f"Could not render invoice {payment.invoice_number}")
		attachments = None
	frappe.sendmail(
		recipients=recipients,
		subject=_("Invoice {0} for your Rent Management subscription").format(payment.invoice_number),
		message=_(
			"<p>Thank you for your payment of {0} for the {1} plan ({2} to {3}).</p>"
			"<p>Your invoice is attached. You can also download it any time from "
			"<a href='{4}'>Subscription & Billing</a>.</p>"
		).format(
			frappe.format_value(payment.amount, {"fieldtype": "Currency", "options": "currency"}, payment),
			payment.plan_title,
			frappe.utils.formatdate(payment.period_start),
			frappe.utils.formatdate(payment.period_end),
			frappe.utils.get_url("/rent/billing"),
		),
		attachments=attachments,
	)


def save_billing_details(data: dict):
	gstin = gst.validate_gstin(data.get("billing_gstin"))
	state = data.get("billing_state") or None
	if gstin:
		state = gst.state_from_gstin(gstin)
	email = (data.get("billing_email") or "").strip()
	if email:
		frappe.utils.validate_email_address(email, throw=True)
	update_subscription(
		billing_name=(data.get("billing_name") or "").strip() or None,
		billing_gstin=gstin or None,
		billing_email=email or None,
		billing_address=data.get("billing_address") or None,
		billing_state=state,
	)


def get_billing_details() -> dict:
	sub = frappe.get_single(SUBSCRIPTION)
	return {
		field: sub.get(field)
		for field in ("billing_name", "billing_gstin", "billing_email", "billing_address", "billing_state")
	}


def record_manual_payment(plan, billing_cycle, amount=0, reference=None, start=None, end=None):
	"""For deals paid outside Razorpay (bank transfer, free months...). Used by `bench rent-subscription`."""
	get_plan(plan)
	payment = frappe.get_doc(
		{
			"doctype": PAYMENT,
			"plan": plan,
			"plan_title": get_plan(plan).get("title", plan),
			"billing_cycle": billing_cycle,
			"amount": flt(amount),
			"currency": get_currency(),
			"payment_method": "Manual",
			"reference": reference,
			"status": "Created",
			"paid_by": frappe.session.user,
		}
	)
	payment.flags.ignore_permissions = True
	payment.insert()
	return apply_payment(payment, start=start, end=end)


# ---------------------------------------------------------------- webhook & reconcile


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Razorpay webhook (events: order.paid, payment.captured). Backup for when the browser
	closes before the checkout callback runs. Orders from other sites are ignored."""
	body = frappe.request.get_data()
	signature = frappe.get_request_header("X-Razorpay-Signature") or ""
	if not razorpay.verify_webhook_signature(body, signature):
		frappe.throw(_("Invalid signature"), frappe.AuthenticationError)

	event = frappe.parse_json(body.decode() or "{}")
	payment = (event.get("payload") or {}).get("payment", {}).get("entity") or {}
	order_id = payment.get("order_id")
	if event.get("event") not in ("order.paid", "payment.captured") or not order_id:
		return {"status": "ignored"}
	if not frappe.db.exists(PAYMENT, {"razorpay_order_id": order_id}):
		return {"status": "ignored"}

	fulfil_order(order_id, payment["id"])
	return {"status": "ok"}


def reconcile_pending_orders():
	"""Catch payments whose checkout callback never reached us (closed tab, lost network)."""
	if not razorpay.is_configured():
		return
	pending = frappe.get_all(
		PAYMENT,
		filters={
			"status": "Created",
			"payment_method": "Razorpay",
			"razorpay_order_id": ("is", "set"),
			"creation": (">=", add_days(nowdate(), -7)),
		},
		pluck="razorpay_order_id",
	)
	for order_id in pending:
		frappe.db.savepoint("reconcile_order")
		try:
			paid = [
				p
				for p in razorpay.get_order_payments(order_id)
				if p.get("status") in ("captured", "authorized")
			]
			if paid:
				fulfil_order(order_id, paid[0]["id"])
		except Exception:
			# skip just this order, keep the ones already reconciled
			frappe.db.rollback(save_point="reconcile_order")
			frappe.log_error(title=_("Could not reconcile Razorpay order {0}").format(order_id))


# ---------------------------------------------------------------- scheduler


def daily():
	"""Refresh the stored status, reconcile open orders and send renewal reminders."""
	reconcile_pending_orders()

	sub = frappe.get_single(SUBSCRIPTION)
	status = get_status(sub)
	if sub.status != status:
		update_subscription()
	if is_enforced():
		send_reminder(sub, status)


def send_reminder(sub, status):
	today = getdate(nowdate())
	if sub.last_reminder_on and getdate(sub.last_reminder_on) == today:
		return

	ends_on = sub.current_period_end or sub.trial_ends_on
	if not ends_on:
		return
	days_left = date_diff(ends_on, today)
	what = _("free trial") if status == "Trial" else _("subscription")

	if days_left in (7, 3, 1):
		subject = _("Your Rent Management {0} ends in {1} days").format(what, days_left)
	elif days_left == -1:
		subject = _("Your Rent Management {0} has ended").format(what)
	elif status == "Expired" and days_left == -(grace_days() + 1):
		subject = _("Your Rent Management account is now read-only")
	else:
		return

	recipients = get_manager_users()
	if recipients:
		billing_url = frappe.utils.get_url("/rent/billing")
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=_(
				"<p>{0}</p><p>Renew your plan to keep creating invoices and recording payments: "
				"<a href='{1}'>{1}</a></p>"
			).format(subject, billing_url),
		)
	update_subscription(last_reminder_on=today)


def skip_if_lapsed() -> bool:
	"""Background jobs that write app data (monthly invoicing) don't run on a lapsed site."""
	return is_enforced() and not is_usable(get_status(frappe.get_single(SUBSCRIPTION)))
