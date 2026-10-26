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
ROOM_FIELDS = ("room_number", "property", "floor", "status", "room_type", "room_rent", "capacity")
PROPERTY_FIELDS = ("property_name", "abbr", "address", "city", "state", "pincode", "is_active")
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
	"property",
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
	"property",
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


def by_property(filters: dict, property=None) -> dict:
	"""Most lists can be narrowed to one building (the switcher in the sidebar)."""
	if property:
		filters["property"] = property
	return filters


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
		"properties": get_properties(),
		"subscription": subscription.get_state(),
	}


# ---------------------------------------------------------------- dashboard


@frappe.whitelist()
def get_dashboard(property=None):
	check_access()
	today = getdate(nowdate())

	rooms = frappe.get_all(
		"Tenant Space", filters=by_property({}, property), fields=["status", "capacity", "occupied_beds"]
	)
	room_status = defaultdict(int)
	for room in rooms:
		room_status[room.status or "Available"] += 1
	beds = sum(max(cint(r.capacity), 1) for r in rooms)
	occupied_beds = sum(cint(r.occupied_beds) for r in rooms)

	open_invoices = frappe.get_all(
		"Tenant Rent Invoice",
		filters=by_property({"docstatus": 1, "outstanding_amount": (">", 0)}, property),
		fields=INVOICE_LIST_FIELDS,
		order_by="due_date asc",
	)
	overdue = [inv for inv in open_invoices if inv.due_date and getdate(inv.due_date) < today]

	return {
		"rooms": {
			"total": len(rooms),
			"by_status": dict(room_status),
			"beds": beds,
			"occupied_beds": occupied_beds,
			"occupancy": round(occupied_beds / beds * 100) if beds else 0,
		},
		"tenants": frappe.db.count(
			"Tenant Space Allotment", by_property({"docstatus": 1, "status": "Active"}, property)
		),
		"this_month": get_month_totals(today, property),
		"outstanding": {
			"amount": sum(flt(inv.outstanding_amount) for inv in open_invoices),
			"count": len(open_invoices),
			"overdue_amount": sum(flt(inv.outstanding_amount) for inv in overdue),
			"overdue_count": len(overdue),
		},
		"trend": [get_month_totals(add_months(today, -offset), property) for offset in range(5, -1, -1)],
		"overdue_invoices": overdue[:6],
		"recent_payments": frappe.get_all(
			"Rent Payment",
			filters=by_property({"docstatus": 1}, property),
			fields=PAYMENT_LIST_FIELDS,
			order_by="payment_date desc, creation desc",
			limit=6,
		),
		"draft_invoices": frappe.db.count("Tenant Rent Invoice", by_property({"docstatus": 0}, property)),
		"pending_deposits": len(get_pending_settlements(property)),
	}


def get_month_totals(date, property=None):
	start, end = get_first_day(date), get_last_day(date)
	invoiced = frappe.get_all(
		"Tenant Rent Invoice",
		filters=by_property(
			{
				"docstatus": 1,
				"billing_month": MONTHS[start.month - 1],
				"billing_year": start.year,
			},
			property,
		),
		pluck="final_amount",
	)
	collected = frappe.get_all(
		"Rent Payment",
		filters=by_property({"docstatus": 1, "payment_date": ("between", (start, end))}, property),
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
def get_rooms(property=None):
	check_access()
	rooms = frappe.get_all(
		"Tenant Space",
		filters=by_property({}, property),
		fields=[
			"name",
			"room_number",
			"property",
			"floor",
			"status",
			"room_type",
			"room_rent",
			"capacity",
			"occupied_beds",
			"tenant",
			"tenant_name",
			"checkin_date",
			"current_allotment",
		],
		order_by="property asc, room_number asc",
	)
	room_types = {rt.name: rt for rt in get_room_types()}
	outstanding = get_outstanding_by("tenant_space_allotment")
	occupants = defaultdict(list)
	for allotment in frappe.get_all(
		"Tenant Space Allotment",
		filters=by_property({"docstatus": 1, "status": "Active"}, property),
		fields=["name", "room", "tenant", "tenant_name", "bed_no", "allotment_date"],
		order_by="bed_no asc",
	):
		allotment.outstanding = outstanding.get(allotment.name, 0)
		occupants[allotment.room].append(allotment)

	for room in rooms:
		room_type = room_types.get(room.room_type) or {}
		room.capacity = max(cint(room.capacity), 1)
		room.is_furnished = room_type.get("is_furnished")
		room.has_attached_bathroom = room_type.get("has_attached_bathroom")
		room.occupants = occupants.get(room.name, [])
		room.free_beds = room.capacity - len(room.occupants)
		room.outstanding = sum(o.outstanding for o in room.occupants)
	return rooms


@frappe.whitelist()
def get_room_types():
	check_access()
	return frappe.get_all(
		"Tenant Space Type", fields=["name", *ROOM_TYPE_FIELDS], order_by="standard_rent asc"
	)


@frappe.whitelist(methods=["POST"])
def create_room(data):
	return save_room(data)


@frappe.whitelist(methods=["POST"])
def save_room(data):
	check_access()
	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc("Tenant Space", data["name"])
		doc.update(pick(data, [f for f in ROOM_FIELDS if f not in ("room_number", "status")]))
		if data.get("status") in ("Reserved", "Under Renovation", "Available") and not doc.occupied_beds:
			doc.status = data["status"]
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Tenant Space", **pick(data, ROOM_FIELDS)}).insert()
	return doc.name


# ---------------------------------------------------------------- buildings


@frappe.whitelist()
def get_properties():
	check_access()
	rooms = defaultdict(lambda: {"rooms": 0, "beds": 0, "occupied_beds": 0})
	for room in frappe.get_all("Tenant Space", fields=["property", "capacity", "occupied_beds"]):
		row = rooms[room.property]
		row["rooms"] += 1
		row["beds"] += max(cint(room.capacity), 1)
		row["occupied_beds"] += cint(room.occupied_beds)
	properties = frappe.get_all(
		"Rent Property", fields=["name", *PROPERTY_FIELDS], order_by="is_active desc, creation asc"
	)
	for prop in properties:
		prop.update(rooms[prop.name])
	return properties


@frappe.whitelist(methods=["POST"])
def save_property(data):
	check_access()
	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc("Rent Property", data["name"])
		doc.update(pick(data, [f for f in PROPERTY_FIELDS if f != "property_name"]))
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Rent Property", **pick(data, PROPERTY_FIELDS)}).insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_room_type(data):
	check_access()
	doc = frappe.get_doc({"doctype": "Tenant Space Type", **pick(data, ROOM_TYPE_FIELDS)}).insert()
	return doc.name


# ---------------------------------------------------------------- tenants


@frappe.whitelist()
def get_tenants(search=None, status=None, property=None):
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
	stays = {
		str(a.tenant): a
		for a in frappe.get_all(
			"Tenant Space Allotment",
			filters={"docstatus": 1, "status": "Active"},
			fields=["tenant", "room", "bed_no", "property"],
		)
	}
	outstanding = get_outstanding_by("tenant")
	for tenant in tenants:
		stay = stays.get(str(tenant.name)) or {}
		tenant.room = stay.get("room")
		tenant.bed_no = stay.get("bed_no")
		tenant.property = stay.get("property")
		tenant.outstanding = outstanding.get(str(tenant.name), 0)
	if property:
		# tenants staying in another building are hidden; those without a room are always shown
		tenants = [t for t in tenants if not t.property or t.property == property]
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
			"bed_no",
			"property",
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
	bed_no=None,
):
	check_access()
	doc = frappe.get_doc(
		{
			"doctype": "Tenant Space Allotment",
			"tenant": tenant,
			"room": room,
			"bed_no": cint(bed_no) or None,
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
def get_billable_allotments(property=None):
	"""Allotments an invoice can be raised against: current tenants and those who moved out."""
	check_access()
	return frappe.get_all(
		"Tenant Space Allotment",
		filters=by_property({"docstatus": 1, "status": ("in", ("Active", "Vacated"))}, property),
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"bed_no",
			"status",
			"rent_amount",
			"allotment_date",
			"vacate_date",
		],
		order_by="status asc, room asc",
	)


# ---------------------------------------------------------------- invoices


@frappe.whitelist()
def get_invoices(
	status=None, billing_month=None, billing_year=None, search=None, start=0, page_length=100, property=None
):
	check_access()
	filters = by_property({"docstatus": ("<", 2)}, property)
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
def get_payments(search=None, mode_of_payment=None, start=0, page_length=100, property=None):
	check_access()
	filters = by_property({"docstatus": 1}, property)
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
def get_deposits(property=None):
	check_access()
	held = frappe.get_all(
		"Tenant Space Allotment",
		filters=by_property({"docstatus": 1, "status": "Active", "security_deposit": (">", 0)}, property),
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
		filters=by_property({"docstatus": 1}, property),
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
	return {"pending": get_pending_settlements(property), "held": held, "settlements": settlements}


def get_pending_settlements(property=None):
	return frappe.get_all(
		"Tenant Space Allotment",
		filters=by_property(
			{
				"docstatus": 1,
				"status": "Vacated",
				"security_deposit": (">", 0),
				"deposit_settlement": ("is", "not set"),
			},
			property,
		),
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
def get_outstanding(as_on_date=None, tenant=None, room=None, overdue_only=0, property=None):
	check_access()
	_columns, data, _message, _chart, summary = rent_outstanding.execute(
		{
			"as_on_date": as_on_date or nowdate(),
			"tenant": tenant,
			"room": room,
			"property": property,
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
			"limits": {key: cint(plan.get(limit)) for key, (limit, _label) in subscription.LIMITS.items()},
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
