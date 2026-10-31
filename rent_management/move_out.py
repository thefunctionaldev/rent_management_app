# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Moving out, as the tenant sees it in the tenant app: notice, the move-out checklist, the deposit.

One page takes the tenant from giving notice to getting their deposit back: the move-out date
and the lock-in, what's checked in the room against the move-in checklist (and what was
charged once the manager completes it), an estimate of the refund (deposit less unpaid bills
and charges), where to send it (their UPI ID or bank account), and the date it's due by:
Settings > Refund Deposits Within days of moving out. Once settled, the breakdown and how it
was paid. Tenants keep the page for a while after moving out, and hear on their phone (and
WhatsApp or email) when the checklist is done and when the deposit is settled. Managers are
reminded the day a refund falls due.
"""

import re

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, getdate, now_datetime, nowdate

ALLOTMENT = "Tenant Space Allotment"
SETTLEMENT = "Security Deposit Settlement"
SETTINGS = "Rent Management Settings"
KEEP_DAYS = 120  # how long after moving out the page stays in the tenant app
UPI = re.compile(r"^[\w.\-]{2,256}@[A-Za-z][A-Za-z0-9.\-]{1,64}$")


def refund_days() -> int:
	value = frappe.db.get_single_value(SETTINGS, "deposit_refund_days")
	return 7 if value is None else cint(value)


def refund_due_on(stay):
	moving = stay.vacate_date or stay.expected_vacate_date
	return add_days(getdate(moving), refund_days()) if moving else None


def stay_for(tenant):
	"""The stay the page is about: the current one, else one they moved out of recently (or
	whose deposit isn't settled yet)."""
	from rent_management.portal import current_stay

	stay = current_stay(tenant)
	if stay:
		return stay
	for row in frappe.get_all(
		ALLOTMENT,
		# a room they moved out of to another one isn't moving out
		filters={"tenant": tenant, "docstatus": 1, "status": "Vacated", "transferred_to": ("is", "not set")},
		fields=["name", "vacate_date", "deposit_settlement", "deposit_collected", "security_deposit"],
		order_by="vacate_date desc",
		limit=1,
	):
		waiting = flt(row.security_deposit) > 0 and row.deposit_collected and not row.deposit_settlement
		if waiting or date_diff(nowdate(), row.vacate_date) <= KEEP_DAYS:
			return frappe.get_doc(ALLOTMENT, row.name)
	return None


def stage(stay) -> str:
	if stay.status == "Active":
		return "notice" if stay.expected_vacate_date else "staying"
	return "settled" if stay.deposit_settlement else "moved_out"


def for_tenant(tenant) -> dict | None:
	from rent_management import inspections

	stay = stay_for(tenant)
	if not stay:
		return None
	today = getdate(nowdate())
	room = frappe.db.get_value("Tenant Space", stay.room, ["room_number", "capacity"], as_dict=True)
	lock_in_ends = (
		add_months(getdate(stay.allotment_date), cint(stay.lock_in_months))
		if cint(stay.lock_in_months)
		else None
	)
	moving_on = (
		getdate(stay.vacate_date or stay.expected_vacate_date)
		if (stay.vacate_date or stay.expected_vacate_date)
		else None
	)
	held = flt(stay.security_deposit) if stay.deposit_collected else 0
	due = refund_due_on(stay)
	data = {
		"stay": stay.name,
		"stage": stage(stay),
		"room": room.room_number if room else stay.room,
		"bed_no": stay.bed_no if room and cint(room.capacity) > 1 else None,
		"property": frappe.db.get_value("Rent Property", stay.property, "property_name") or stay.property,
		"allotment_date": stay.allotment_date,
		"notice_period_days": cint(stay.notice_period_days),
		"earliest_date": add_days(today, cint(stay.notice_period_days)),
		"lock_in_ends": lock_in_ends,
		"breaks_lock_in": bool(lock_in_ends and (moving_on or add_days(today, cint(stay.notice_period_days))) < lock_in_ends),
		"notice_given_on": stay.notice_given_on,
		"moving_on": moving_on,
		"days_left": max(date_diff(moving_on, today), 0) if moving_on and stay.status == "Active" else None,
		"vacate_date": stay.vacate_date,
		"deposit": flt(stay.security_deposit),
		"deposit_held": held,
		"refund_days": refund_days(),
		"refund_due_on": due if held else None,
		"refund_overdue": bool(held and due and not stay.deposit_settlement and today > due),
		"refund_upi_id": stay.refund_upi_id,
		"refund_bank_details": stay.refund_bank_details,
		"checklist": checklist(stay),
	}  # fmt: skip
	if stay.deposit_settlement:
		data["settlement"] = settlement(stay.deposit_settlement)
	else:
		unpaid = flt(
			sum(
				flt(i.outstanding_amount)
				for i in frappe.get_all(
					"Tenant Rent Invoice",
					filters={
						"tenant_space_allotment": stay.name,
						"docstatus": 1,
						"outstanding_amount": (">", 0),
					},
					fields=["outstanding_amount"],
				)
			),
			2,
		)
		charges = flt(data["checklist"]["charges"]) if data["checklist"]["status"] == "Completed" else 0
		left = held - unpaid - charges
		data["estimate"] = {
			"unpaid": unpaid,
			"charges": charges,
			"refund": max(flt(left, 2), 0),
			"owes": max(flt(-left, 2), 0),
		}
	data["move_in_items"] = (
		inspections.move_in_items(stay.name) if data["checklist"]["status"] != "Completed" else []
	)
	return data


def checklist(stay) -> dict:
	"""The move-out checklist, once the manager completes it (a draft may still change)."""
	from rent_management import inspections

	doc = inspections.existing(stay.name, "Move-out")
	if not doc or doc.status != "Completed":
		return {"status": doc.status if doc else None, "items": [], "charges": 0}
	return {
		"status": "Completed",
		"date": doc.inspection_date,
		"notes": doc.notes,
		"charges": flt(doc.total_charges),
		"items": [
			{
				"item": r.item,
				"quantity": r.quantity,
				"move_in_condition": r.move_in_condition,
				"condition": r.condition,
				"changed": bool(r.move_in_condition and r.condition != r.move_in_condition),
				"notes": r.notes,
				"charge": flt(r.charge),
			}
			for r in doc.items
		],
	}


def settlement(name) -> dict:
	doc = frappe.get_doc(SETTLEMENT, name)
	return {
		"date": doc.settlement_date,
		"deposit": flt(doc.security_deposit),
		"deductions": [
			{"reason": d.reason, "description": d.description, "amount": flt(d.amount)}
			for d in doc.deductions
		],
		"total_deductions": flt(doc.total_deductions),
		"rent_adjusted": flt(doc.rent_adjusted),
		"refund": flt(doc.refund_amount),
		"owes": flt(doc.balance_payable_by_tenant),
		"mode": doc.mode_of_refund,
		"reference": doc.reference_no,
		"remarks": doc.remarks,
	}


def save_refund_details(tenant, upi_id=None, bank_details=None):
	stay = stay_for(tenant)
	if not stay:
		frappe.throw(_("You have no stay to move out of."))
	if stay.deposit_settlement:
		frappe.throw(_("Your deposit is already settled."))
	upi_id = (upi_id or "").strip() or None
	bank_details = (bank_details or "").strip() or None
	if upi_id and not UPI.match(upi_id):
		frappe.throw(_("{0} doesn't look like a UPI ID (like name@okbank).").format(upi_id))
	if not (upi_id or bank_details):
		frappe.throw(_("Add a UPI ID or bank account for the refund."))
	stay.db_set(
		{"refund_upi_id": upi_id, "refund_bank_details": bank_details, "refund_details_on": now_datetime()}
	)


# ---------------------------------------------------------------- telling the tenant


def tell_tenant(tenant, subject, message, message_type=None, params=None):
	"""A phone notification in the tenant app, and WhatsApp or email when it matters."""
	from rent_management import notifications

	t = frappe.db.get_value(
		"Tenant", tenant, ["name", "first_name", "full_name", "mobile_no", "email_id", "user"], as_dict=True
	)
	if not t:
		return
	if t.user:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": t.user,
				"type": "Alert",
				"subject": subject,
				"email_content": message,
				"link": "/tenant/moving-out",
			}
		).insert(ignore_permissions=True)
	if message_type:
		notifications.send(message_type, t, message, params or [], subject=subject)


def on_checklist_update(doc, method=None):
	"""Room Inspection on_update: tell the tenant when their move-out checklist is completed."""
	if doc.inspection_type != "Move-out" or doc.status != "Completed":
		return
	before = doc.get_doc_before_save()
	if before and before.status == "Completed":
		return
	tenant = frappe.db.get_value(ALLOTMENT, doc.allotment, "tenant")
	charges = flt(doc.total_charges)
	tell_tenant(
		tenant,
		_("Your move-out checklist is done"),
		_("{0} charged for damages or missing items. See the details in the app.").format(
			frappe.utils.fmt_money(charges, currency="INR")
		)
		if charges
		else _("Everything was found as it was at move-in. Nothing is charged."),
	)


def on_settlement_submit(doc, method=None):
	"""Security Deposit Settlement on_submit: tell the tenant what they get back."""
	from rent_management.notifications import money

	first = frappe.db.get_value("Tenant", doc.tenant, "first_name") or doc.tenant_name
	if flt(doc.balance_payable_by_tenant) > 0:
		amount, what = money(doc.balance_payable_by_tenant), _("still to pay")
	else:
		amount, what = money(doc.refund_amount), _("refunded")
	params = [first, money(doc.security_deposit), amount, what]
	tell_tenant(
		doc.tenant,
		_("Your deposit is settled"),
		_("Hello {0}, your deposit of {1} is settled: {2} {3}. See the breakdown in the app.").format(
			*params
		),
		message_type="Deposit",
		params=params,
	)


# ---------------------------------------------------------------- reminding managers


def remind():
	"""Daily: managers hear the day a deposit refund falls due, and on Mondays which are late."""
	from rent_management.portal import notify_managers

	today = getdate(nowdate())
	days = refund_days()
	waiting = frappe.get_all(
		ALLOTMENT,
		filters={
			"docstatus": 1,
			"status": "Vacated",
			"deposit_collected": 1,
			"security_deposit": (">", 0),
			"deposit_settlement": ("is", "not set"),
			"transferred_to": ("is", "not set"),
			"vacate_date": ("<=", add_days(today, -days)),
		},
		fields=["name", "tenant", "tenant_name", "room", "property", "vacate_date", "security_deposit"],
	)
	late = []
	for row in waiting:
		due = add_days(getdate(row.vacate_date), days)
		if due == today:
			notify_managers(
				_("Refund {0}'s deposit today").format(row.tenant_name),
				_("{0} moved out of room {1} on {2}. Their deposit refund is due today.").format(
					row.tenant_name, row.room, frappe.utils.formatdate(row.vacate_date)
				),
				link="/rent/deposits",
				property=row.property,
			)
		else:
			late.append(row)
	if late and today.weekday() == 0:
		notify_managers(
			_("{0} deposit refunds are late").format(len(late)),
			", ".join(f"{r.tenant_name} ({r.room})" for r in late[:10]),
			link="/rent/deposits",
		)
