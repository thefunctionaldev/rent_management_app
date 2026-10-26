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

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, getdate, now_datetime, nowdate

from rent_management import razorpay

SUBSCRIPTION = "Rent Subscription"
PAYMENT = "Rent Subscription Payment"
MANAGER_ROLE = "Rent Manager"
CYCLES = {"Monthly": 1, "Yearly": 12}  # months per billing cycle

# max_rooms / max_users: 0 means unlimited
DEFAULT_PLANS = {
	"starter": {
		"title": "Starter",
		"description": "For a single PG or a small building.",
		"monthly": 499,
		"yearly": 4990,
		"max_rooms": 15,
		"max_users": 2,
		"features": [
			"Up to 15 rooms",
			"2 manager logins",
			"Rent invoices and payments",
			"Deposit settlement",
		],
	},
	"growth": {
		"title": "Growth",
		"description": "For growing hostels and PGs.",
		"monthly": 1499,
		"yearly": 14990,
		"max_rooms": 60,
		"max_users": 5,
		"features": [
			"Up to 60 rooms",
			"5 manager logins",
			"Everything in Starter",
			"Outstanding and aging report",
		],
	},
	"pro": {
		"title": "Pro",
		"description": "For large properties and multiple buildings.",
		"monthly": 3999,
		"yearly": 39990,
		"max_rooms": 0,
		"max_users": 0,
		"features": [
			"Unlimited rooms",
			"Unlimited manager logins",
			"Everything in Growth",
			"Priority support",
		],
	},
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
	return {"rooms": frappe.db.count("Tenant Space"), "users": len(get_manager_users())}


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
		"limits": {"rooms": cint(plan.get("max_rooms")), "users": cint(plan.get("max_users"))},
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


def get_limit(key: str) -> int:
	sub = frappe.get_single(SUBSCRIPTION)
	return cint((get_plans().get(sub.plan or trial_plan()) or {}).get(f"max_{key}"))


def check_room_limit(doc, method=None):
	if skip_enforcement():
		return
	limit = get_limit("rooms")
	if limit and frappe.db.count("Tenant Space") >= limit:
		frappe.throw(
			_(
				"Your plan allows up to {0} rooms. Upgrade from "
				"<a href='/rent/billing'>Subscription & Billing</a> to add more."
			).format(limit),
			PlanLimitError,
			title=_("Room limit reached"),
		)


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
	for key, label in (("rooms", _("rooms")), ("users", _("Rent Manager users"))):
		limit = cint(limits.get(f"max_{key}"))
		if limit and usage[key] > limit:
			frappe.throw(
				_(
					"The {0} plan allows {1} {2}, but you have {3}. Remove some first or choose a bigger plan."
				).format(limits.get("title", plan), limit, label, usage[key]),
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
	amount = get_price(plan, billing_cycle)
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
	payment.flags.ignore_permissions = True
	frappe.flags.updating_rent_subscription = True
	try:
		payment.save()
	finally:
		frappe.flags.updating_rent_subscription = False

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
