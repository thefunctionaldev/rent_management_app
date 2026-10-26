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
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from rent_management import (
	data_import,
	gst,
	notifications,
	portal,
	profit,
	razorpay,
	rent_collection,
	saas,
	subscription,
)
from rent_management.rent_management_system import billing
from rent_management.rent_management_system.doctype.rent_property.rent_property import get_default_property
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.report.rent_outstanding import rent_outstanding

ALLOWED_ROLES = ("System Manager", "Rent Manager")
AGREEMENT_FORMAT = "Rent Agreement"

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
ROOM_FIELDS = (
	"room_number",
	"property",
	"floor",
	"status",
	"room_type",
	"room_rent",
	"capacity",
	"has_meter",
	"electricity_rate",
)
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
		"is_control_site": saas.is_control_site() and "System Manager" in frappe.get_roles(),
		"agreement_defaults": {
			field: frappe.db.get_single_value("Rent Management Settings", f"default_{key}")
			for field, key in (
				("agreement_months", "agreement_months"),
				("lock_in_months", "lock_in_months"),
				("notice_period_days", "notice_days"),
				("rent_increase_percent", "rent_increase_percent"),
			)
		},
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
		"moving_out": frappe.get_all(
			"Tenant Space Allotment",
			filters=by_property(
				{"docstatus": 1, "status": "Active", "expected_vacate_date": ("<=", add_days(today, 30))},
				property,
			),
			fields=["name", "tenant", "tenant_name", "room", "bed_no", "expected_vacate_date"],
			order_by="expected_vacate_date asc",
		),
		"agreements_ending": frappe.get_all(
			"Tenant Space Allotment",
			filters=by_property(
				{
					"docstatus": 1,
					"status": "Active",
					"expected_vacate_date": ("is", "not set"),
					"agreement_end_date": ("between", (add_days(today, -30), add_days(today, 30))),
				},
				property,
			),
			fields=["name", "tenant", "tenant_name", "room", "agreement_end_date"],
			order_by="agreement_end_date asc",
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
			"has_meter",
			"electricity_rate",
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
			"agreement_months",
			"agreement_end_date",
			"lock_in_months",
			"notice_period_days",
			"rent_increase_percent",
			"next_rent_increase_date",
			"notice_given_on",
			"expected_vacate_date",
		],
		order_by="allotment_date desc",
	)
	revisions = defaultdict(list)
	for row in frappe.get_all(
		"Rent Revision",
		filters={
			"parenttype": "Tenant Space Allotment",
			"parent": ("in", [a.name for a in allotments] or [""]),
		},
		fields=["parent", "effective_from", "old_rent", "new_rent", "reason"],
		order_by="effective_from desc",
	):
		revisions[row.parent].append(row)
	for allotment in allotments:
		allotment.rent_revisions = revisions.get(allotment.name, [])
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
	tenant_data = tenant.as_dict()
	tenant_data.pop("aadhar_card_number", None)  # '*****'; see reveal_aadhaar
	return {
		"tenant": tenant_data,
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
		values = pick(data, TENANT_FIELDS)
		if not values.get("aadhar_card_number") and not data.get("clear_aadhaar"):
			values.pop("aadhar_card_number", None)  # left blank in the form: keep the saved number
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Tenant", **pick(data, TENANT_FIELDS)}).insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def reveal_aadhaar(name):
	check_access()
	return frappe.get_doc("Tenant", name).reveal_aadhar()


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
	agreement_months=None,
	lock_in_months=None,
	notice_period_days=None,
	rent_increase_percent=None,
):
	check_access()
	optional = lambda value: None if value in (None, "") else value  # noqa: E731
	doc = frappe.get_doc(
		{
			"doctype": "Tenant Space Allotment",
			"tenant": tenant,
			"room": room,
			"bed_no": cint(bed_no) or None,
			"agreement_months": optional(agreement_months),
			"lock_in_months": optional(lock_in_months),
			"notice_period_days": optional(notice_period_days),
			"rent_increase_percent": optional(rent_increase_percent),
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
def give_notice(allotment, notice_date=None, vacate_date=None):
	check_access()
	return frappe.get_doc("Tenant Space Allotment", allotment).give_notice(notice_date, vacate_date)


@frappe.whitelist(methods=["POST"])
def withdraw_notice(allotment):
	check_access()
	frappe.get_doc("Tenant Space Allotment", allotment).withdraw_notice()


@frappe.whitelist(methods=["POST"])
def revise_rent(allotment, new_rent, effective_from=None, reason=None):
	check_access()
	frappe.get_doc("Tenant Space Allotment", allotment).revise_rent(new_rent, effective_from, reason)


@frappe.whitelist()
def download_agreement(allotment):
	check_access()
	doc = frappe.get_doc("Tenant Space Allotment", allotment)
	doc.check_permission("print")
	send_pdf(
		f"Agreement-{doc.name}",
		frappe.get_print(doc.doctype, doc.name, print_format=AGREEMENT_FORMAT, as_pdf=True),
	)


def send_pdf(filename, content):
	frappe.local.response.filename = f"{filename}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"


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
	allotments = frappe.get_all(
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
	electricity = defaultdict(float)
	for row in frappe.get_all(
		"Meter Reading Share",
		filters={"parenttype": "Meter Reading", "rent_invoice": ("is", "not set")},
		fields=["tenant_space_allotment", "amount"],
	):
		electricity[row.tenant_space_allotment] += flt(row.amount)
	for allotment in allotments:
		# added to the next invoice automatically
		allotment.pending_electricity = electricity.get(allotment.name, 0)
	return allotments


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
	upi_link = rent_collection.get_upi_link(doc)
	return {
		"invoice": doc.as_dict(),
		"online": rent_collection.get_payment_options(),
		"upi_link": upi_link,
		"upi_qr": rent_collection.qr_data_uri(upi_link) if upi_link else None,
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
def get_payment_link(name):
	check_access()
	return rent_collection.get_payment_link(name)


@frappe.whitelist(methods=["POST"])
def check_online_payment(name):
	"""Look up the invoice's payment link on Razorpay and record what was paid."""
	check_access()
	return rent_collection.sync_payment_link(frappe.get_doc("Tenant Rent Invoice", name))


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


# ---------------------------------------------------------------- electricity


@frappe.whitelist()
def get_meter_rooms(property=None):
	"""Rooms with a meter and their last reading, for entering this month's readings."""
	check_access()
	rooms = frappe.get_all(
		"Tenant Space",
		filters=by_property({"has_meter": 1}, property),
		fields=["name", "room_number", "property", "floor", "occupied_beds", "electricity_rate"],
		order_by="property asc, room_number asc",
	)
	default_rate = frappe.db.get_single_value("Rent Management Settings", "electricity_rate")
	for room in rooms:
		last = frappe.get_all(
			"Meter Reading",
			filters={"room": room.name},
			fields=["reading", "reading_date"],
			order_by="reading_date desc",
			limit=1,
		)
		room.last_reading = last[0].reading if last else None
		room.last_reading_date = last[0].reading_date if last else None
		room.rate = flt(room.electricity_rate) or flt(default_rate)
	return {"rooms": rooms, "default_rate": flt(default_rate)}


@frappe.whitelist(methods=["POST"])
def save_meter_readings(reading_date, readings):
	"""Save several rooms' readings at once; each row is saved or reported on its own."""
	check_access()
	results = []
	for row in frappe.parse_json(readings) or []:
		if row.get("reading") in (None, ""):
			continue
		frappe.db.savepoint("meter_reading")
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Meter Reading",
					"room": row["room"],
					"reading_date": reading_date,
					"reading": flt(row["reading"]),
					"meter_replaced": cint(row.get("meter_replaced")),
				}
			).insert()
			results.append({"room": row["room"], "name": doc.name, "units": doc.units, "amount": doc.amount})
		except Exception as e:
			frappe.db.rollback(save_point="meter_reading")
			frappe.clear_last_message()
			results.append({"room": row["room"], "error": data_import.strip_html(str(e))})
	return results


@frappe.whitelist()
def get_meter_readings(property=None, room=None, limit=100):
	check_access()
	filters = by_property({}, property)
	if room:
		filters["room"] = room
	readings = frappe.get_all(
		"Meter Reading",
		filters=filters,
		fields=[
			"name",
			"room",
			"property",
			"reading_date",
			"previous_reading",
			"reading",
			"units",
			"rate",
			"amount",
			"status",
		],
		order_by="reading_date desc, room asc",
		limit=cint(limit),
	)
	shares = defaultdict(list)
	for share in frappe.get_all(
		"Meter Reading Share",
		filters={"parenttype": "Meter Reading", "parent": ("in", [r.name for r in readings] or [""])},
		fields=["parent", "tenant_name", "units", "amount", "rent_invoice"],
		order_by="idx asc",
	):
		shares[share.parent].append(share)
	for reading in readings:
		reading.shares = shares.get(reading.name, [])
	return readings


@frappe.whitelist(methods=["POST"])
def delete_meter_reading(name):
	check_access()
	frappe.delete_doc("Meter Reading", name)


# ---------------------------------------------------------------- tenant app


@frappe.whitelist(methods=["POST"])
def invite_tenant(name):
	"""Give the tenant a login for the tenant app and email them a set-password link."""
	check_access()
	link = portal.invite_tenant(name)
	# managers without email set up can share the link themselves (WhatsApp...)
	return {"link": link, "emailed": notifications.email_configured()}


REQUEST_LIST_FIELDS = [
	"name",
	"subject",
	"category",
	"priority",
	"status",
	"tenant",
	"tenant_name",
	"room",
	"property",
	"description",
	"resolution",
	"raised_via",
	"creation",
	"resolved_on",
]


@frappe.whitelist()
def get_requests(status=None, property=None):
	check_access()
	filters = by_property({}, property)
	if status == "open":
		filters["status"] = ("in", ("Open", "In Progress"))
	elif status:
		filters["status"] = status
	counts = defaultdict(int)
	for row in frappe.get_all("Maintenance Request", filters=by_property({}, property), pluck="status"):
		counts[row] += 1
	requests = frappe.get_all(
		"Maintenance Request",
		filters=filters,
		fields=REQUEST_LIST_FIELDS,
		order_by="creation desc",
		limit=300,
	)
	# open first, most urgent first, newest first within that
	status_order = {"Open": 0, "In Progress": 1, "Resolved": 2, "Closed": 3}
	priority_order = {"High": 0, "Medium": 1, "Low": 2}
	requests.sort(key=lambda r: (status_order.get(r.status, 9), priority_order.get(r.priority, 9)))
	return {"requests": requests, "counts": dict(counts)}


@frappe.whitelist(methods=["POST"])
def save_request(data):
	check_access()
	data = frappe.parse_json(data)
	fields = ("subject", "category", "priority", "status", "description", "resolution", "tenant")
	if data.get("name"):
		doc = frappe.get_doc("Maintenance Request", data["name"])
		doc.update(pick(data, [f for f in fields if f != "tenant"]))
		doc.save()
	else:
		doc = frappe.get_doc(
			{"doctype": "Maintenance Request", **pick(data, fields), "raised_via": "Manager"}
		).insert()
	return doc.name


@frappe.whitelist()
def get_payments_to_confirm(property=None):
	"""Payments tenants reported in the tenant app ("I've paid"), waiting for the landlord."""
	check_access()
	return frappe.get_all(
		"Rent Payment",
		filters=by_property({"docstatus": 0}, property),
		fields=PAYMENT_LIST_FIELDS,
		order_by="creation asc",
	)


@frappe.whitelist(methods=["POST"])
def confirm_payment(name):
	check_access()
	doc = frappe.get_doc("Rent Payment", name)
	doc.submit()
	return doc.name


@frappe.whitelist(methods=["POST"])
def reject_payment(name, reason=None):
	check_access()
	doc = frappe.get_doc("Rent Payment", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only unconfirmed payments can be rejected."))
	invoice = frappe.get_doc("Tenant Rent Invoice", doc.rent_invoice)
	invoice.add_comment(
		"Info",
		_("Payment of {0} reported by the tenant (ref {1}) was rejected{2}").format(
			doc.amount, doc.reference_no or "-", f": {reason}" if reason else ""
		),
	)
	frappe.delete_doc("Rent Payment", name)


# ---------------------------------------------------------------- expenses

EXPENSE_FIELDS = (
	"property",
	"expense_date",
	"category",
	"amount",
	"paid_to",
	"mode_of_payment",
	"reference_no",
	"description",
	"receipt",
)


@frappe.whitelist()
def get_expenses(property=None, from_date=None, to_date=None, category=None):
	check_access()
	filters = by_property({}, property)
	if from_date and to_date:
		filters["expense_date"] = ("between", (from_date, to_date))
	if category:
		filters["category"] = category
	return {
		"expenses": frappe.get_all(
			"Property Expense",
			filters=filters,
			fields=["name", *EXPENSE_FIELDS],
			order_by="expense_date desc, creation desc",
			limit=500,
		),
		"categories": frappe.get_meta("Property Expense").get_field("category").options.split("\n"),
	}


@frappe.whitelist(methods=["POST"])
def save_expense(data):
	check_access()
	data = frappe.parse_json(data)
	values = pick(data, EXPENSE_FIELDS)
	if not values.get("property"):
		values["property"] = get_default_property()
	if data.get("name"):
		doc = frappe.get_doc("Property Expense", data["name"])
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Property Expense", **values}).insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_expense(name):
	check_access()
	frappe.delete_doc("Property Expense", name)


@frappe.whitelist()
def get_profit_and_loss(months=12, property=None):
	check_access()
	if not subscription.has_feature("profit_report"):
		frappe.throw(
			_("The profit and loss report is part of the Growth and Pro plans."), subscription.PlanLimitError
		)
	return profit.get_profit_and_loss(min(max(cint(months), 1), 36), property)


# ---------------------------------------------------------------- settings

SETTINGS_FIELDS = (
	"auto_generate_invoices",
	"auto_submit_invoices",
	"rent_due_day",
	"electricity_rate",
	"upi_id",
	"upi_payee_name",
	"razorpay_enabled",
	"razorpay_key_id",
	"send_reminders",
	"remind_days_before",
	"remind_on_due_date",
	"overdue_reminder_interval",
	"overdue_reminder_limit",
	"send_receipts",
	"notify_by_whatsapp",
	"notify_by_email",
	"whatsapp_phone_number_id",
	"landlord_name",
	"landlord_phone",
	"landlord_address",
	"default_agreement_months",
	"default_lock_in_months",
	"default_notice_days",
	"default_rent_increase_percent",
	"agreement_terms",
)
# write-only: the browser only learns whether they are set
SECRET_FIELDS = ("razorpay_key_secret", "razorpay_webhook_secret", "whatsapp_token")


@frappe.whitelist()
def get_settings():
	check_access()
	settings = frappe.get_single("Rent Management Settings")
	values = {field: settings.get(field) for field in SETTINGS_FIELDS}
	for field in SECRET_FIELDS:
		values[f"{field}_set"] = bool(settings.get_password(field, raise_exception=False))
	own_whatsapp = bool(settings.whatsapp_phone_number_id and values["whatsapp_token_set"])
	return {
		"settings": values,
		"whatsapp": {
			"available": bool(notifications.get_whatsapp_account()),
			"source": "own" if own_whatsapp else ("plan" if notifications.get_whatsapp_account() else None),
			"in_plan": subscription.has_feature("whatsapp"),
		},
		"email_configured": notifications.email_configured(),
		"webhook_url": frappe.utils.get_url("/api/method/rent_management.rent_collection.razorpay_webhook"),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(data):
	check_access()
	data = frappe.parse_json(data)
	settings = frappe.get_single("Rent Management Settings")
	terms = data.get("agreement_terms")
	if terms and "<" not in terms:
		# typed in a plain textarea: keep the lines when printed
		data["agreement_terms"] = "".join(
			f"<p>{frappe.utils.escape_html(line)}</p>" for line in terms.splitlines() if line.strip()
		)
	settings.update(pick(data, SETTINGS_FIELDS))
	for field in SECRET_FIELDS:
		if data.get(field):
			settings.set(field, data[field])
		elif data.get(f"clear_{field}"):
			settings.set(field, None)
	settings.save()
	return get_settings()


@frappe.whitelist()
def get_message_log(start=0, page_length=50):
	check_access()
	return frappe.get_all(
		"Rent Message Log",
		fields=[
			"name",
			"creation",
			"message_type",
			"channel",
			"status",
			"recipient",
			"tenant",
			"tenant_name",
			"rent_invoice",
			"error",
		],
		order_by="creation desc",
		start=cint(start),
		page_length=cint(page_length),
	)


@frappe.whitelist(methods=["POST"])
def send_rent_reminder(name):
	check_access()
	statuses = notifications.send_reminder(name)
	if not statuses:
		frappe.throw(
			_("Nothing was sent: the tenant has no WhatsApp number or email, or both channels are off.")
		)
	return statuses


@frappe.whitelist()
def export_data():
	"""All the landlord's data as an Excel workbook."""
	check_access()
	from frappe.desk.utils import provide_binary_file

	from rent_management import export

	provide_binary_file(f"rent-management-{frappe.local.site}-{nowdate()}", "xlsx", export.get_workbook())


# ---------------------------------------------------------------- import


@frappe.whitelist()
def get_import_template(kind):
	check_access()
	from frappe.desk.utils import provide_binary_file

	provide_binary_file(f"{kind}-import-template", "xlsx", data_import.get_template(kind))


@frappe.whitelist(methods=["POST"])
def import_data(kind, filename, content, dry_run=1):
	check_access()
	return data_import.run(kind, filename, content, dry_run=cint(dry_run))


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
			"invoice_number",
		],
		order_by="paid_on desc",
		limit=50,
	)
	vendor = gst.get_vendor()
	return {
		"subscription": subscription.get_state(),
		"plans": plans,
		"payments": payments,
		"billing_details": subscription.get_billing_details(),
		"gst": {
			"registered": bool(vendor.gstin),
			"rate": gst.gst_rate(),
			"included": gst.prices_include_gst(),
			"states": sorted(set(gst.STATE_CODES.values())),
		},
		"online_payments": razorpay.is_configured(),
		"support_email": frappe.conf.get("rent_support_email"),
	}


@frappe.whitelist(methods=["POST"])
def save_billing_details(data):
	check_access()
	subscription.save_billing_details(frappe.parse_json(data))
	return subscription.get_billing_details()


@frappe.whitelist()
def download_subscription_invoice(name):
	"""PDF of a subscription tax invoice (Rent Managers can't open the desk print view)."""
	check_access()
	payment = frappe.get_doc(subscription.PAYMENT, name)
	if not payment.invoice_number:
		frappe.throw(_("This payment has no invoice."))
	frappe.local.response.filename = payment.invoice_number.replace("/", "-") + ".pdf"
	frappe.local.response.filecontent = frappe.get_print(
		subscription.PAYMENT, name, print_format=subscription.INVOICE_PRINT_FORMAT, as_pdf=True
	)
	frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def create_subscription_checkout(plan, billing_cycle):
	check_access()
	return subscription.create_checkout(plan, billing_cycle)


@frappe.whitelist(methods=["POST"])
def verify_subscription_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
	check_access()
	return subscription.verify_checkout(razorpay_order_id, razorpay_payment_id, razorpay_signature)
