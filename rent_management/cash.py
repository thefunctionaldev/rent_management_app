# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The cash book: who is holding how much cash.

Cash is held by whoever took it in: a cash Rent Payment counts for the user who recorded (or
confirmed) it (Rent Payment.collected_by). Cash going out comes from whoever paid it: a cash
Property Expense (paid_by), which includes cash salaries and advances. A Cash Handover moves
cash from one person to another (a warden to the owner) once the one receiving it confirms.

	balance = collected - spent + received in handovers - handed over
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, now_datetime, nowdate

HANDOVER = "Cash Handover"
CASH = "Cash"


# ---------------------------------------------------------------- who holds it (doc events)


def set_collected_by(doc, method=None):
	"""Rent Payment before_submit: the cash is with whoever records (or confirms) it."""
	if doc.mode_of_payment == CASH and not doc.collected_by:
		doc.collected_by = frappe.session.user
	elif doc.mode_of_payment != CASH:
		doc.collected_by = None


def set_paid_by(doc, method=None):
	"""Property Expense validate: cash paid out by whoever records it."""
	if doc.mode_of_payment == CASH and not doc.paid_by:
		doc.paid_by = frappe.session.user
	elif doc.mode_of_payment != CASH:
		doc.paid_by = None


# ---------------------------------------------------------------- movements


def movements(user=None, property=None, from_date=None, to_date=None) -> list[dict]:
	"""Every cash movement, newest first: in (collected, received) and out (spent, handed over)."""
	rows = []
	base = {"property": property} if property else {}

	def dates(field):
		if from_date and to_date:
			return {field: ("between", (from_date, to_date))}
		if to_date:
			return {field: ("<=", to_date)}
		return {}

	for p in frappe.get_all(
		"Rent Payment",
		filters={**base, **dates("payment_date"), "docstatus": 1, "mode_of_payment": CASH,
			**({"collected_by": user} if user else {"collected_by": ("is", "set")})},
		fields=["name", "payment_date", "amount", "tenant_name", "room", "rent_invoice", "collected_by", "property"],
	):  # fmt: skip
		rows.append(
			{
				"date": p.payment_date,
				"user": p.collected_by,
				"kind": "Collected",
				"amount": flt(p.amount),
				"description": _("Rent from {0} (room {1})").format(p.tenant_name, p.room),
				"doctype": "Rent Payment",
				"name": p.name,
				"property": p.property,
			}
		)
	for e in frappe.get_all(
		"Property Expense",
		filters={**base, **dates("expense_date"), "mode_of_payment": CASH,
			**({"paid_by": user} if user else {"paid_by": ("is", "set")})},
		fields=["name", "expense_date", "amount", "category", "paid_to", "paid_by", "property"],
	):  # fmt: skip
		rows.append(
			{
				"date": e.expense_date,
				"user": e.paid_by,
				"kind": "Spent",
				"amount": -flt(e.amount),
				"description": " · ".join(filter(None, [e.category, e.paid_to])),
				"doctype": "Property Expense",
				"name": e.name,
				"property": e.property,
			}
		)
	handover_filters = {**base, **dates("handed_on"), "status": "Confirmed"}
	for h in frappe.get_all(
		HANDOVER, filters=handover_filters, fields=["name", "handed_on", "amount", "from_user", "from_name", "to_user", "to_name", "note", "property"]
	):  # fmt: skip
		if not user or h.from_user == user:
			rows.append(
				{
					"date": h.handed_on,
					"user": h.from_user,
					"kind": "Handed over",
					"amount": -flt(h.amount),
					"description": _("To {0}").format(h.to_name or h.to_user)
					+ (f" · {h.note}" if h.note else ""),
					"doctype": HANDOVER,
					"name": h.name,
					"property": h.property,
				}
			)
		if not user or h.to_user == user:
			rows.append(
				{
					"date": h.handed_on,
					"user": h.to_user,
					"kind": "Received",
					"amount": flt(h.amount),
					"description": _("From {0}").format(h.from_name or h.from_user)
					+ (f" · {h.note}" if h.note else ""),
					"doctype": HANDOVER,
					"name": h.name,
					"property": h.property,
				}
			)
	# newest day first; on a day, money in before money out
	order = {"Collected": 0, "Received": 1, "Spent": 2, "Handed over": 3}
	rows.sort(key=lambda r: (-getdate(r["date"]).toordinal(), order[r["kind"]]))
	return rows


def balances(property=None) -> list[dict]:
	"""Cash each person holds now."""
	totals = defaultdict(lambda: {"collected": 0.0, "spent": 0.0, "received": 0.0, "handed_over": 0.0})
	field = {"Collected": "collected", "Spent": "spent", "Received": "received", "Handed over": "handed_over"}
	for row in movements(property=property):
		totals[row["user"]][field[row["kind"]]] += abs(row["amount"])
	pending = defaultdict(float)
	for h in frappe.get_all(HANDOVER, filters={"status": "Pending"}, fields=["from_user", "amount"]):
		pending[h.from_user] += flt(h.amount)
	names = dict(
		frappe.get_all(
			"User", filters={"name": ("in", list(totals) or [""])}, fields=["name", "full_name"], as_list=True
		)
	)
	result = []
	for user, t in totals.items():
		balance = flt(t["collected"] - t["spent"] + t["received"] - t["handed_over"], 2)
		result.append(
			{
				"user": user,
				"full_name": names.get(user) or user,
				**t,
				"balance": balance,
				"pending": pending[user],
			}
		)
	return sorted(result, key=lambda r: -r["balance"])


def balance_of(user) -> float:
	return next((r["balance"] for r in balances() if r["user"] == user), 0.0)


# ---------------------------------------------------------------- handing over


def receivers() -> list[dict]:
	"""Who cash can be handed to: managers, and staff logins."""
	from rent_management import access

	users = set(
		frappe.get_all(
			"Has Role",
			filters={"role": ("in", (*access.MANAGER_ROLES, access.STAFF_ROLE)), "parenttype": "User"},
			pluck="parent",
		)
	) - {"Administrator", "Guest", frappe.session.user}
	return frappe.get_all(
		"User",
		filters={"name": ("in", list(users) or [""]), "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name asc",
	)


def hand_over(to_user, amount, note=None, handed_on=None) -> str:
	amount = flt(amount, 2)
	if to_user not in [r.name for r in receivers()]:
		frappe.throw(_("Choose a manager or a staff member to hand it to."))
	held = balance_of(frappe.session.user)
	pending = flt(
		sum(
			frappe.get_all(
				HANDOVER, filters={"from_user": frappe.session.user, "status": "Pending"}, pluck="amount"
			)
		)
	)
	if amount > held - pending + 0.5:
		frappe.throw(
			_("You hold {0} in cash{1}.").format(
				money(held - pending), _(" not yet handed over") if pending else ""
			)
		)
	from rent_management import access

	staff = access.staff_access()
	doc = frappe.get_doc(
		{
			"doctype": HANDOVER,
			"from_user": frappe.session.user,
			"to_user": to_user,
			"amount": amount,
			"handed_on": handed_on or nowdate(),
			"note": (note or "").strip()[:500] or None,
			"property": staff.building if staff else None,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": to_user,
			"type": "Alert",
			"subject": _("{0} handed you {1} in cash").format(doc.from_name or doc.from_user, money(amount)),
			"email_content": _("Confirm it in the cash book once you have it.")
			+ (f" {doc.note}" if doc.note else ""),
			"link": "/rent/cash",
		}
	).insert(ignore_permissions=True)
	return doc.name


def confirm(name, accept=1):
	doc = frappe.get_doc(HANDOVER, name)
	if doc.to_user != frappe.session.user:
		frappe.throw(
			_("Only {0} can confirm this.").format(doc.to_name or doc.to_user), frappe.PermissionError
		)
	if doc.status != "Pending":
		frappe.throw(_("This handover is already {0}.").format(doc.status.lower()))
	doc.status = "Confirmed" if int(accept) else "Rejected"
	doc.confirmed_on = now_datetime()
	doc.save(ignore_permissions=True)


def cancel(name):
	"""The one who handed it over takes back a handover not yet confirmed."""
	doc = frappe.get_doc(HANDOVER, name)
	if doc.from_user != frappe.session.user or doc.status != "Pending":
		frappe.throw(
			_("Only your own handovers waiting to be confirmed can be cancelled."), frappe.PermissionError
		)
	frappe.delete_doc(HANDOVER, name, ignore_permissions=True)


def money(amount) -> str:
	from rent_management.notifications import money as fmt

	return fmt(amount)


# ---------------------------------------------------------------- the page


def get_cash_book(property=None, from_date=None, to_date=None) -> dict:
	"""Managers: everyone's cash. Staff: their own."""
	from rent_management import access

	me = frappe.session.user
	manager = access.is_manager()
	from_date = getdate(from_date or get_first_day(nowdate()))
	to_date = getdate(to_date or nowdate())
	everyone = balances(property if manager else None)
	mine = next((r for r in everyone if r["user"] == me), {"balance": 0.0, "pending": 0.0})
	pending_fields = ["name", "from_user", "from_name", "to_user", "to_name", "amount", "handed_on", "note"]
	return {
		"manager": manager,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"holders": [r for r in everyone if abs(r["balance"]) >= 0.5 or r["pending"]] if manager else [],
		"total": sum(r["balance"] for r in everyone) if manager else None,
		"me": mine,
		"to_confirm": frappe.get_all(
			HANDOVER,
			filters={"to_user": me, "status": "Pending"},
			fields=pending_fields,
			order_by="creation asc",
		),
		"my_pending": frappe.get_all(
			HANDOVER,
			filters={"from_user": me, "status": "Pending"},
			fields=pending_fields,
			order_by="creation desc",
		),
		"entries": movements(None if manager else me, property if manager else None, from_date, to_date),
		"receivers": receivers(),
		"yesterday": str(add_days(nowdate(), -1)),
	}
