# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""JSON API used by the /rent frontend.

Every endpoint is restricted to System Manager / Rent Manager. Writes go through the
regular DocType controllers, so all validations (room availability, duplicate
invoices, overpayment...) apply exactly as they do in the desk.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from rent_management import razorpay, subscription
from rent_management.rent_management_system import billing
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.report.rent_outstanding import rent_outstanding

ALLOWED_ROLES = ("System Manager", "Rent Manager")

TENANT_FIELDS = (
	"first_name",
	"middle_name",
	"last_name",
	"status",
	"mobile_no",
	"email_id",
	"permanent_address",
	"gender",
	"aadhar_card_number",
	"occupation",
	"workspace",
	"salary",
)
ROOM_FIELDS = ("room_number", "floor", "status", "room_type", "room_rent")
ROOM_TYPE_FIELDS = (
	"type",
	"description",
	"standard_rent",
	"deposit_applicable",
	"security_deposit",
	"is_furnished",
	"has_attached_bathroom",
)
INVOICE_LIST_FIELDS = [
	"name",
	"tenant",
	"tenant_name",
	"room",
	"tenant_space_allotment",
	"billing_month",
	"billing_year",
	"posting_date",
	"due_date",
	"final_amount",
	"paid_amount",
	"outstanding_amount",
	"status",
	"docstatus",
]
PAYMENT_LIST_FIELDS = [
	"name",
	"tenant",
	"tenant_name",
	"rent_invoice",
	"room",
	"payment_date",
	"mode_of_payment",
	"amount",
	"reference_no",
	"docstatus",
]


def check_access():
	frappe.only_for(ALLOWED_ROLES)


def has_app_permission():
	"""Show the Rent Management tile on the apps screen only to managers."""
	return bool(set(frappe.get_roles()) & set(ALLOWED_ROLES))


def pick(data, fields):
	data = frappe.parse_json(data) or {}
	return {key: data[key] for key in fields if key in data}


# ---------------------------------------------------------------- session


@frappe.whitelist()
def get_boot():
	check_access()
	user = frappe.get_cached_doc("User", frappe.session.user)
	currency = frappe.db.get_default("currency") or "INR"
	return {
		"user": user.name,
		"full_name": user.full_name,
		"user_image": user.user_image,
		"currency": currency,
		"currency_symbol": frappe.db.get_value("Currency", currency, "symbol") or currency,
		"number_format": frappe.db.get_default("number_format") or "#,##,###.##",
		"site_name": frappe.local.site,
		"months": MONTHS,
		"today": nowdate(),
		"subscription": subscription.get_state(),
	}


# ---------------------------------------------------------------- dashboard


@frappe.whitelist()
def get_dashboard():
	check_access()
	today = getdate(nowdate())

	rooms = frappe.get_all("Tenant Space", fields=["status"])
	room_status = defaultdict(int)
	for room in rooms:
		room_status[room.status or "Available"] += 1

	open_invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=INVOICE_LIST_FIELDS,
		order_by="due_date asc",
	)
	overdue = [inv for inv in open_invoices if inv.due_date and getdate(inv.due_date) < today]

	return {
		"rooms": {
			"total": len(rooms),
			"by_status": dict(room_status),
			"occupancy": round(room_status["Occupied"] / len(rooms) * 100) if rooms else 0,
		},
		"tenants": frappe.db.count("Tenant", {"status": "Active"}),
		"this_month": get_month_totals(today),
		"outstanding": {
			"amount": sum(flt(inv.outstanding_amount) for inv in open_invoices),
			"count": len(open_invoices),
			"overdue_amount": sum(flt(inv.outstanding_amount) for inv in overdue),
			"overdue_count": len(overdue),
		},
		"trend": [get_month_totals(add_months(today, -offset)) for offset in range(5, -1, -1)],
		"overdue_invoices": overdue[:6],
		"recent_payments": frappe.get_all(
			"Rent Payment",
			filters={"docstatus": 1},
			fields=PAYMENT_LIST_FIELDS,
			order_by="payment_date desc, creation desc",
			limit=6,
		),
		"draft_invoices": frappe.db.count("Tenant Rent Invoice", {"docstatus": 0}),
		"pending_deposits": len(get_pending_settlements()),
	}


def get_month_totals(date):
	start, end = get_first_day(date), get_last_day(date)
	invoiced = frappe.get_all(
		"Tenant Rent Invoice",
		filters={
			"docstatus": 1,
			"billing_month": MONTHS[start.month - 1],
			"billing_year": start.year,
		},
		pluck="final_amount",
	)
	collected = frappe.get_all(
		"Rent Payment",
		filters={"docstatus": 1, "payment_date": ("between", (start, end))},
		pluck="amount",
	)
	return {
		"label": start.strftime("%b %Y"),
		"month": MONTHS[start.month - 1],
		"year": start.year,
		"invoiced": sum(flt(v) for v in invoiced),
		"collected": sum(flt(v) for v in collected),
	}


# ---------------------------------------------------------------- rooms


@frappe.whitelist()
def get_rooms():
	check_access()
	rooms = frappe.get_all(
		"Tenant Space",
		fields=[
			"name",
			"room_number",
			"floor",
			"status",
			"room_type",
			"room_rent",
			"tenant",
			"tenant_name",
			"checkin_date",
			"current_allotment",
		],
		order_by="room_number asc",
	)
	room_types = {rt.name: rt for rt in get_room_types()}
	outstanding = get_outstanding_by("tenant_space_allotment")
	for room in rooms:
		room_type = room_types.get(room.room_type) or {}
		room.is_furnished = room_type.get("is_furnished")
		room.has_attached_bathroom = room_type.get("has_attached_bathroom")
		room.outstanding = outstanding.get(room.current_allotment, 0)
	return rooms


@frappe.whitelist()
def get_room_types():
	check_access()
	return frappe.get_all(
		"Tenant Space Type", fields=["name", *ROOM_TYPE_FIELDS], order_by="standard_rent asc"
	)


@frappe.whitelist(methods=["POST"])
def create_room(data):
	check_access()
	doc = frappe.get_doc({"doctype": "Tenant Space", **pick(data, ROOM_FIELDS)}).insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_room_type(data):
	check_access()
	doc = frappe.get_doc({"doctype": "Tenant Space Type", **pick(data, ROOM_TYPE_FIELDS)}).insert()
	return doc.name


# ---------------------------------------------------------------- tenants


@frappe.whitelist()
def get_tenants(search=None, status=None):
	check_access()
	filters = {"status": status} if status else {}
	or_filters = None
	if search:
		or_filters = [
			["full_name", "like", f"%{search}%"],
			["mobile_no", "like", f"%{search}%"],
			["email_id", "like", f"%{search}%"],
		]
	tenants = frappe.get_all(
		"Tenant",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"full_name",
			"mobile_no",
			"email_id",
			"status",
			"occupation",
			"display_picture",
			"creation",
		],
		order_by="full_name asc",
	)
	rooms = {
		str(a.tenant): a.room
		for a in frappe.get_all(
			"Tenant Space Allotment",
			filters={"docstatus": 1, "status": "Active"},
			fields=["tenant", "room"],
		)
	}
	outstanding = get_outstanding_by("tenant")
	for tenant in tenants:
		tenant.room = rooms.get(str(tenant.name))
		tenant.outstanding = outstanding.get(str(tenant.name), 0)
	return tenants


@frappe.whitelist()
def get_tenant(name):
	check_access()
	tenant = frappe.get_doc("Tenant", name)
	tenant.check_permission("read")
	allotments = frappe.get_all(
		"Tenant Space Allotment",
		filters={"tenant": name, "docstatus": ("<", 2)},
		fields=[
			"name",
			"room",
			"room_type",
			"allotment_date",
			"vacate_date",
			"status",
			"rent_amount",
			"security_deposit",
			"deposit_collected",
			"deposit_collected_on",
			"deposit_settlement",
			"docstatus",
		],
		order_by="allotment_date desc",
	)
	invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters={"tenant": name, "docstatus": ("<", 2)},
		fields=INVOICE_LIST_FIELDS,
		order_by="billing_year desc, posting_date desc",
	)
	payments = frappe.get_all(
		"Rent Payment",
		filters={"tenant": name, "docstatus": 1},
		fields=PAYMENT_LIST_FIELDS,
		order_by="payment_date desc",
	)
	submitted = [inv for inv in invoices if inv.docstatus == 1]
	return {
		"tenant": tenant.as_dict(),
		"allotments": allotments,
		"invoices": invoices,
		"payments": payments,
		"totals": {
			"invoiced": sum(flt(inv.final_amount) for inv in submitted),
			"paid": sum(flt(p.amount) for p in payments),
			"outstanding": sum(flt(inv.outstanding_amount) for inv in submitted),
		},
	}


@frappe.whitelist(methods=["POST"])
def save_tenant(data):
	check_access()
	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc("Tenant", data["name"])
		doc.update(pick(data, TENANT_FIELDS))
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Tenant", **pick(data, TENANT_FIELDS)}).insert()
	return doc.name


# ---------------------------------------------------------------- allotments


@frappe.whitelist(methods=["POST"])
def allot_room(
	tenant,
	room,
	allotment_date=None,
	rent_amount=None,
	security_deposit=None,
	deposit_collected=0,
	notes=None,
):
	check_access()
	doc = frappe.get_doc(
		{
			"doctype": "Tenant Space Allotment",
			"tenant": tenant,
			"room": room,
			"allotment_date": allotment_date or nowdate(),
			"rent_amount": flt(rent_amount) or None,
			"security_deposit": flt(security_deposit) or None,
			"deposit_collected": cint(deposit_collected),
			"deposit_collected_on": (allotment_date or nowdate()) if cint(deposit_collected) else None,
			"notes": notes,
		}
	)
	doc.insert()
	doc.submit()
	return doc.name


@frappe.whitelist(methods=["POST"])
def vacate_room(allotment, vacate_date=None):
	check_access()
	doc = frappe.get_doc("Tenant Space Allotment", allotment)
	doc.check_permission("write")
	doc.vacate(vacate_date)
	return doc.name


@frappe.whitelist(methods=["POST"])
def mark_deposit_collected(allotment, collected_on=None):
	check_access()
	doc = frappe.get_doc("Tenant Space Allotment", allotment)
	doc.deposit_collected = 1
	doc.deposit_collected_on = collected_on or nowdate()
	doc.save()
	return doc.name


@frappe.whitelist()
def get_billable_allotments():
	"""Allotments an invoice can be raised against: current tenants and those who moved out."""
	check_access()
	return frappe.get_all(
		"Tenant Space Allotment",
		filters={"docstatus": 1, "status": ("in", ("Active", "Vacated"))},
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"status",
			"rent_amount",
			"allotment_date",
			"vacate_date",
		],
		order_by="status asc, room asc",
	)


# ---------------------------------------------------------------- invoices


@frappe.whitelist()
def get_invoices(status=None, billing_month=None, billing_year=None, search=None, start=0, page_length=100):
	check_access()
	filters = {"docstatus": ("<", 2)}
	if billing_month:
		filters["billing_month"] = billing_month
	if billing_year:
		filters["billing_year"] = cint(billing_year)

	or_filters = None
	if search:
		or_filters = [
			["name", "like", f"%{search}%"],
			["tenant_name", "like", f"%{search}%"],
			["room", "like", f"%{search}%"],
		]

	counts = defaultdict(int)
	for row in frappe.get_all("Tenant Rent Invoice", filters=filters, or_filters=or_filters, pluck="status"):
		counts[row] += 1

	if status:
		filters["status"] = status
	invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters=filters,
		or_filters=or_filters,
		fields=INVOICE_LIST_FIELDS,
		order_by="posting_date desc, name desc",
		start=cint(start),
		page_length=cint(page_length),
	)
	return {"invoices": invoices, "counts": dict(counts)}


@frappe.whitelist()
def get_invoice(name):
	check_access()
	doc = frappe.get_doc("Tenant Rent Invoice", name)
	doc.check_permission("read")
	return {
		"invoice": doc.as_dict(),
		"payments": frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": name, "docstatus": 1},
			fields=PAYMENT_LIST_FIELDS,
			order_by="payment_date asc",
		),
		"mobile_no": frappe.db.get_value("Tenant", doc.tenant, "mobile_no"),
		"print_url": f"/printview?doctype=Tenant%20Rent%20Invoice&name={name}"
		"&format=Tenant%20Rent%20Invoice%20Print%20Format&no_letterhead=1",
	}


@frappe.whitelist(methods=["POST"])
def create_invoice(
	tenant_space_allotment,
	billing_month,
	billing_year,
	charges=None,
	discount_amount=0,
	posting_date=None,
	due_date=None,
	remarks=None,
	submit=0,
):
	check_access()
	doc = frappe.get_doc(
		{
			"doctype": "Tenant Rent Invoice",
			"tenant_space_allotment": tenant_space_allotment,
			"billing_month": billing_month,
			"billing_year": cint(billing_year),
			"discount_amount": flt(discount_amount),
			"posting_date": posting_date or nowdate(),
			"due_date": due_date or None,
			"remarks": remarks,
			"charges": [
				pick(row, ("charge_type", "description", "amount"))
				for row in frappe.parse_json(charges) or []
				if flt(row.get("amount"))
			],
		}
	).insert()
	if cint(submit):
		doc.submit()
	return doc.name


@frappe.whitelist(methods=["POST"])
def submit_invoice(name):
	check_access()
	doc = frappe.get_doc("Tenant Rent Invoice", name)
	doc.submit()
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_invoice(name):
	check_access()
	if frappe.db.get_value("Tenant Rent Invoice", name, "docstatus") != 0:
		frappe.throw(_("Only draft invoices can be deleted."))
	frappe.delete_doc("Tenant Rent Invoice", name)


@frappe.whitelist(methods=["POST"])
def generate_invoices(billing_month, billing_year, submit=0):
	check_access()
	created = billing.generate_invoices(billing_month, cint(billing_year), submit=cint(submit))
	return {"created": created}


# ---------------------------------------------------------------- payments


@frappe.whitelist()
def get_payments(search=None, mode_of_payment=None, start=0, page_length=100):
	check_access()
	filters = {"docstatus": 1}
	if mode_of_payment:
		filters["mode_of_payment"] = mode_of_payment
	or_filters = None
	if search:
		or_filters = [
			["name", "like", f"%{search}%"],
			["tenant_name", "like", f"%{search}%"],
			["rent_invoice", "like", f"%{search}%"],
			["reference_no", "like", f"%{search}%"],
		]
	return frappe.get_all(
		"Rent Payment",
		filters=filters,
		or_filters=or_filters,
		fields=PAYMENT_LIST_FIELDS,
		order_by="payment_date desc, creation desc",
		start=cint(start),
		page_length=cint(page_length),
	)


@frappe.whitelist(methods=["POST"])
def record_payment(
	rent_invoice, amount, mode_of_payment="Cash", payment_date=None, reference_no=None, remarks=None
):
	check_access()
	tenant = frappe.db.get_value("Tenant Rent Invoice", rent_invoice, "tenant")
	doc = frappe.get_doc(
		{
			"doctype": "Rent Payment",
			"tenant": tenant,
			"rent_invoice": rent_invoice,
			"amount": flt(amount),
			"mode_of_payment": mode_of_payment,
			"payment_date": payment_date or nowdate(),
			"reference_no": reference_no,
			"remarks": remarks,
		}
	).insert()
	doc.submit()
	return doc.name


# ---------------------------------------------------------------- deposits


@frappe.whitelist()
def get_deposits():
	check_access()
	held = frappe.get_all(
		"Tenant Space Allotment",
		filters={"docstatus": 1, "status": "Active", "security_deposit": (">", 0)},
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"allotment_date",
			"security_deposit",
			"deposit_collected",
			"deposit_collected_on",
		],
		order_by="allotment_date desc",
	)
	settlements = frappe.get_all(
		"Security Deposit Settlement",
		filters={"docstatus": 1},
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"tenant_space_allotment",
			"settlement_date",
			"security_deposit",
			"total_deductions",
			"rent_adjusted",
			"refund_amount",
			"balance_payable_by_tenant",
			"mode_of_refund",
		],
		order_by="settlement_date desc",
	)
	return {"pending": get_pending_settlements(), "held": held, "settlements": settlements}


def get_pending_settlements():
	return frappe.get_all(
		"Tenant Space Allotment",
		filters={
			"docstatus": 1,
			"status": "Vacated",
			"security_deposit": (">", 0),
			"deposit_settlement": ("is", "not set"),
		},
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"allotment_date",
			"vacate_date",
			"security_deposit",
			"deposit_collected",
		],
		order_by="vacate_date desc",
	)


def make_settlement(allotment, deductions=None, adjust_outstanding_rent=1, **kwargs):
	return frappe.get_doc(
		{
			"doctype": "Security Deposit Settlement",
			"tenant_space_allotment": allotment,
			"adjust_outstanding_rent": cint(adjust_outstanding_rent),
			"deductions": [
				pick(row, ("reason", "description", "amount"))
				for row in frappe.parse_json(deductions) or []
				if flt(row.get("amount"))
			],
			**kwargs,
		}
	)


@frappe.whitelist(methods=["POST"])
def preview_settlement(allotment, deductions=None, adjust_outstanding_rent=1):
	check_access()
	doc = make_settlement(allotment, deductions, adjust_outstanding_rent)
	doc.update_amounts()
	return {
		field: doc.get(field)
		for field in (
			"security_deposit",
			"outstanding_rent",
			"total_deductions",
			"rent_adjusted",
			"refund_amount",
			"balance_payable_by_tenant",
		)
	}


@frappe.whitelist(methods=["POST"])
def settle_deposit(
	allotment,
	deductions=None,
	adjust_outstanding_rent=1,
	mode_of_refund=None,
	reference_no=None,
	settlement_date=None,
	remarks=None,
):
	check_access()
	doc = make_settlement(
		allotment,
		deductions,
		adjust_outstanding_rent,
		mode_of_refund=mode_of_refund,
		reference_no=reference_no,
		settlement_date=settlement_date or nowdate(),
		remarks=remarks,
	).insert()
	doc.submit()
	return doc.name


# ---------------------------------------------------------------- reports


@frappe.whitelist()
def get_outstanding(as_on_date=None, tenant=None, room=None, overdue_only=0):
	check_access()
	_columns, data, _message, _chart, summary = rent_outstanding.execute(
		{
			"as_on_date": as_on_date or nowdate(),
			"tenant": tenant,
			"room": room,
			"overdue_only": cint(overdue_only),
		}
	)
	return {
		"rows": data,
		"summary": summary,
		"buckets": [
			{"fieldname": fieldname, "label": str(label), "amount": sum(flt(row[fieldname]) for row in data)}
			for fieldname, label, _limit in rent_outstanding.AGING_BUCKETS
		],
	}


def get_outstanding_by(field):
	totals = defaultdict(float)
	for row in frappe.get_all(
		"Tenant Rent Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=[field, "outstanding_amount"],
	):
		totals[str(row[field])] += flt(row.outstanding_amount)
	return totals


# ---------------------------------------------------------------- subscription


@frappe.whitelist()
def get_billing():
	check_access()
	plans = [
		{
			"key": key,
			"title": plan.get("title", key),
			"description": plan.get("description"),
			"monthly": flt(plan.get("monthly")),
			"yearly": flt(plan.get("yearly")),
			"max_rooms": cint(plan.get("max_rooms")),
			"max_users": cint(plan.get("max_users")),
			"features": plan.get("features") or [],
		}
		for key, plan in subscription.get_plans().items()
	]
	payments = frappe.get_all(
		subscription.PAYMENT,
		filters={"status": "Paid"},
		fields=[
			"name",
			"plan_title",
			"billing_cycle",
			"amount",
			"currency",
			"payment_method",
			"paid_on",
			"period_start",
			"period_end",
			"bonus_days",
			"razorpay_payment_id",
		],
		order_by="paid_on desc",
		limit=50,
	)
	return {
		"subscription": subscription.get_state(),
		"plans": plans,
		"payments": payments,
		"online_payments": razorpay.is_configured(),
		"support_email": frappe.conf.get("rent_support_email"),
	}


@frappe.whitelist(methods=["POST"])
def create_subscription_checkout(plan, billing_cycle):
	check_access()
	return subscription.create_checkout(plan, billing_cycle)


@frappe.whitelist(methods=["POST"])
def verify_subscription_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
	check_access()
	return subscription.verify_checkout(razorpay_order_id, razorpay_payment_id, razorpay_signature)
