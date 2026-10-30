# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Tenants refer friends and get money off their rent.

Each tenant has a referral code and a link to the listing page with it (?ref=CODE). An enquiry
from that link (or a lead a manager marks "referred by") is a referral. When the friend moves
in, their first rent invoice gets the friend's discount. When they have paid a rent invoice in
full, the referral is earned: the referrer is told, and the reward comes off the referrer's
next rent invoice (or a manager pays it out, e.g. to someone who has moved out).

Credits are negative "Referral Credit" charges on the invoice, so the invoice, payments and
reports work as usual. A cancelled or deleted invoice gives its credits back.

	rent_referral_reward  Hello {{1}}, {{2}} moved in and paid their first rent, so you get {{3}}
	                      off your next rent. Thank you for referring them!
"""

import random
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate, random_string

from rent_management import notifications

REFERRAL = "Rent Referral"
SETTINGS = "Rent Management Settings"
CHARGE = "Referral Credit"


def settings():
	return frappe.get_cached_doc(SETTINGS)


def enabled() -> bool:
	return bool(cint(settings().referrals_enabled))


def digits(mobile) -> str:
	return re.sub(r"\D", "", str(mobile or ""))[-10:]


# ---------------------------------------------------------------- codes and links


def code_for(tenant) -> str:
	"""The tenant's referral code, made the first time it's needed: e.g. DEEPAK42."""
	code = frappe.db.get_value("Tenant", tenant, "referral_code")
	if code:
		return code
	first = frappe.db.get_value("Tenant", tenant, "first_name") or "FRIEND"
	stem = re.sub(r"[^A-Z]", "", first.upper())[:8] or "FRIEND"
	for attempt in range(20):
		# two digits are easy to say; four letters and digits if those are taken
		suffix = (
			str(random.randint(10, 99)) if attempt < 5 else re.sub(r"[^A-Z0-9]", "", random_string(4).upper())
		)
		code = f"{stem}{suffix}"
		if not frappe.db.exists("Tenant", {"referral_code": code}):
			break
	frappe.db.set_value("Tenant", tenant, "referral_code", code, update_modified=False)
	return code


def tenant_for(code) -> str | None:
	code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
	return frappe.db.get_value("Tenant", {"referral_code": code}) if code else None


def share_url(code) -> str:
	from rent_management import leads

	return f"{leads.listing_url()}?ref={code}"


def share_text(tenant, code) -> str:
	s = settings()
	name = frappe.db.get_value("Tenant", tenant, "first_name")
	offer = (
		_(" Use my link and you get {0} off your first month.").format(
			notifications.money(s.referral_friend_discount)
		)
		if flt(s.referral_friend_discount)
		else ""
	)
	return _("I stay at {0} and like it here. Have a look if you need a place.{1} {2}").format(
		landlord_name(), offer, share_url(code)
	) + (f" - {name}" if name else "")


def landlord_name() -> str:
	buildings = frappe.get_all("Rent Property", filters={"is_active": 1}, pluck="property_name", limit=2)
	return buildings[0] if len(buildings) == 1 else (settings().landlord_name or _("my PG"))


# ---------------------------------------------------------------- leads


def on_enquiry(lead, ref):
	"""A listing page enquiry that came through a tenant's link."""
	if not (enabled() and ref):
		return
	referrer = tenant_for(ref)
	if not referrer:
		return
	if digits(frappe.db.get_value("Tenant", referrer, "mobile_no")) == digits(lead.mobile_no):
		return  # referring yourself
	lead.source = "Referral"
	lead.referred_by = referrer


def sync_lead(lead, method=None):
	"""Rent Lead on_update: keep its referral in step."""
	if not lead.referred_by:
		return
	name = frappe.db.get_value(REFERRAL, {"lead": lead.name})
	if not name:
		if lead.status == "Lost" or frappe.db.exists(
			REFERRAL, {"friend_mobile": lead.mobile_no, "status": ("!=", "Not Eligible")}
		):
			return  # already referred by someone
		frappe.get_doc(
			{
				"doctype": REFERRAL,
				"referrer": lead.referred_by,
				"lead": lead.name,
				"friend_name": lead.lead_name,
				"friend_mobile": lead.mobile_no,
				"property": lead.property,
				"status": "Enquired",
			}
		).insert(ignore_permissions=True)
		return
	doc = frappe.get_doc(REFERRAL, name)
	if doc.status == "Enquired":
		doc.update(
			{"referrer": lead.referred_by, "friend_name": lead.lead_name, "friend_mobile": lead.mobile_no}
		)
		if lead.status == "Lost":
			doc.status = "Not Eligible"
		doc.save(ignore_permissions=True)
	elif doc.status == "Not Eligible" and lead.status not in ("Lost", "Moved In"):
		doc.db_set("status", "Enquired")


def on_move_in(lead, tenant, allotment):
	"""The friend moved in: their discount is due on the first rent, the reward on payment."""
	name = frappe.db.get_value(REFERRAL, {"lead": lead.name})
	if not name:
		return
	s = settings()
	doc = frappe.get_doc(REFERRAL, name)
	doc.update(
		{
			"status": "Moved In",
			"new_tenant": tenant,
			"allotment": allotment,
			"property": frappe.db.get_value("Tenant Space Allotment", allotment, "property"),
			"reward_amount": flt(s.referral_reward),
			"friend_discount": flt(s.referral_friend_discount),
		}
	)
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------- credits on invoices


def add_credits(invoice):
	"""A new invoice: the friend's discount on their first rent, and rewards the tenant earned."""
	from rent_management import fees

	invoice.set("charges", [c for c in invoice.charges if c.charge_type != CHARGE])  # copied by an amendment
	owed = frappe.get_all(
		REFERRAL,
		filters={
			"allotment": invoice.tenant_space_allotment,
			"status": ("in", ("Moved In", "Earned", "Rewarded")),
			"friend_discount": (">", 0),
			"friend_discount_invoice": ("is", "not set"),
		},
		fields=["name", "friend_discount as amount", "referrer_name"],
	)
	for row in owed:
		row.description = _("Discount for being referred by {0}").format(row.referrer_name)
	rewards = frappe.get_all(
		REFERRAL,
		filters={"referrer": invoice.tenant, "status": "Earned", "reward_invoice": ("is", "not set")},
		fields=["name", "reward_amount as amount", "friend_name"],
		order_by="earned_on asc",
	)
	for row in rewards:
		row.description = _("Reward for referring {0}").format(row.friend_name)

	room = fees.base_amount(invoice)
	for row in owed + rewards:
		if 0 < flt(row.amount) <= room:  # an invoice never goes below zero
			invoice.append(
				"charges",
				{
					"charge_type": CHARGE,
					"description": row.description,
					"amount": -flt(row.amount),
					"referral": row.name,
				},
			)
			room -= flt(row.amount)


def link_credits(invoice, method=None):
	"""After insert: mark the credits as used by this invoice."""
	for row in invoice.charges:
		if row.charge_type != CHARGE or not row.referral:
			continue
		doc = frappe.get_doc(REFERRAL, row.referral)
		if doc.allotment == invoice.tenant_space_allotment and not doc.friend_discount_invoice:
			doc.friend_discount_invoice = invoice.name
		elif str(doc.referrer) == str(invoice.tenant) and doc.status == "Earned":
			doc.update(
				{
					"status": "Rewarded",
					"reward_invoice": invoice.name,
					"rewarded_on": nowdate(),
					"reward_mode": "Rent Credit",
				}
			)
		doc.save(ignore_permissions=True)


def release_credits(invoice, method=None):
	"""A cancelled or deleted invoice gives its credits back, for the next one."""
	for name in frappe.get_all(REFERRAL, filters={"friend_discount_invoice": invoice.name}, pluck="name"):
		frappe.db.set_value(REFERRAL, name, "friend_discount_invoice", None)
	for name in frappe.get_all(REFERRAL, filters={"reward_invoice": invoice.name}, pluck="name"):
		frappe.db.set_value(
			REFERRAL,
			name,
			{"status": "Earned", "reward_invoice": None, "rewarded_on": None, "reward_mode": None},
		)


# ---------------------------------------------------------------- earning the reward


def on_payment(payment, method=None):
	"""Rent Payment on_submit / on_cancel: the friend has (or no longer has) paid a rent in full."""
	allotment = frappe.db.get_value("Tenant Rent Invoice", payment.rent_invoice, "tenant_space_allotment")
	name = frappe.db.get_value(REFERRAL, {"allotment": allotment, "status": ("in", ("Moved In", "Earned"))})
	if not name:
		return
	paid = frappe.db.exists(
		"Tenant Rent Invoice",
		{"tenant_space_allotment": allotment, "docstatus": 1, "outstanding_amount": ("<=", 0)},
	)
	doc = frappe.get_doc(REFERRAL, name)
	if doc.status == "Moved In" and paid and payment.mode_of_payment != "Security Deposit":
		doc.update({"status": "Earned", "earned_on": nowdate()})
		doc.save(ignore_permissions=True)
		tell_referrer(doc)
	elif doc.status == "Earned" and not paid:
		doc.update({"status": "Moved In", "earned_on": None})
		doc.save(ignore_permissions=True)


def tell_referrer(doc):
	from rent_management.portal import notify_managers

	notify_managers(
		_("Referral reward earned by {0}").format(doc.referrer_name),
		_("{0} referred {1}, who has moved in and paid. {2} comes off {0}'s next rent.").format(
			doc.referrer_name, doc.friend_name, notifications.money(doc.reward_amount)
		),
		link="/rent/leads?tab=referrals",
	)
	tenant = frappe.db.get_value(
		"Tenant", doc.referrer, ["name", "first_name", "full_name", "mobile_no", "email_id"], as_dict=True
	)
	params = [tenant.first_name or tenant.full_name, doc.friend_name, notifications.money(doc.reward_amount)]
	text = _(
		"Hello {0}, {1} moved in and paid their first rent, so you get {2} off your next rent. "
		"Thank you for referring them!"
	).format(*params)
	try:
		notifications.send("Referral", tenant, text, params, subject=_("You earned a referral reward"))
	except Exception:
		frappe.log_error(title=f"Referral message for {doc.name}")


def pay_out(name, note=None):
	"""Given in cash instead (e.g. the referrer has moved out): a Marketing expense."""
	doc = frappe.get_doc(REFERRAL, name)
	if doc.status != "Earned":
		frappe.throw(_("Only an earned reward that isn't credited yet can be paid out."))
	building = doc.property or frappe.db.get_value(
		"Tenant Space Allotment",
		{"tenant": doc.referrer, "docstatus": 1},
		"property",
		order_by="allotment_date desc",
	)
	if building:
		frappe.get_doc(
			{
				"doctype": "Property Expense",
				"property": building,
				"expense_date": nowdate(),
				"category": "Marketing",
				"amount": doc.reward_amount,
				"paid_to": doc.referrer_name,
				"mode_of_payment": "Cash",
				"description": _("Referral reward for {0}").format(doc.friend_name),
			}
		).insert()
	doc.update(
		{"status": "Rewarded", "rewarded_on": nowdate(), "reward_mode": "Paid Out", "note": note or doc.note}
	)
	doc.save()


# ---------------------------------------------------------------- lists


FIELDS = ["name", "referrer", "referrer_name", "friend_name", "friend_mobile", "status", "lead", "new_tenant",
	"property", "reward_amount", "friend_discount", "earned_on", "rewarded_on", "reward_mode", "reward_invoice",
	"creation"]  # fmt: skip


def get_referrals(property=None) -> dict:
	filters = {"property": property} if property else {}
	rows = frappe.get_all(REFERRAL, filters=filters, fields=FIELDS, order_by="creation desc", limit=300)
	return {
		"referrals": rows,
		"enabled": enabled(),
		"moved_in": sum(1 for r in rows if r.status in ("Moved In", "Earned", "Rewarded")),
		"rewarded": sum(flt(r.reward_amount) for r in rows if r.status == "Rewarded"),
		"to_reward": sum(flt(r.reward_amount) for r in rows if r.status == "Earned"),
	}


def for_tenant(tenant) -> dict:
	"""The tenant app's Refer a friend page."""
	s = settings()
	code = code_for(tenant)
	rows = frappe.get_all(
		REFERRAL,
		filters={"referrer": tenant},
		fields=["friend_name", "status", "reward_amount", "creation", "rewarded_on", "reward_mode"],
		order_by="creation desc",
	)
	return {
		"code": code,
		"url": share_url(code),
		"text": share_text(tenant, code),
		"reward": flt(s.referral_reward),
		"friend_discount": flt(s.referral_friend_discount),
		"referrals": [
			{
				"friend_name": (r.friend_name or "").split(" ")[0],  # their own business, mostly
				"status": r.status,
				"reward_amount": r.reward_amount,
				"since": r.creation.date(),
			}
			for r in rows
		],
		"earned": sum(flt(r.reward_amount) for r in rows if r.status in ("Earned", "Rewarded")),
	}


def referrer_on_listing(ref) -> dict | None:
	"""For the listing page: who sent them, and their discount."""
	if not enabled():
		return None
	tenant = tenant_for(ref)
	if not tenant:
		return None
	return {
		"name": frappe.db.get_value("Tenant", tenant, "first_name"),
		"discount": flt(settings().referral_friend_discount),
	}
