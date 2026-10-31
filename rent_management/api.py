# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""JSON API used by the /rent frontend.

Every endpoint is restricted to System Manager / Rent Manager. Writes go through the
regular DocType controllers, so all validations (room availability, duplicate
invoices, overpayment...) apply exactly as they do in the desk.
"""

from collections import defaultdict
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from rent_management import (
	access,
	activity,
	cash,
	checkin,
	data_import,
	documents,
	fees,
	gst,
	inspections,
	leads,
	ledger,
	mess,
	move_out,
	notices,
	notifications,
	owner_summary,
	pdf,
	pictures,
	portal,
	profit,
	razorpay,
	receipts,
	referrals,
	register,
	rent_collection,
	saas,
	salaries,
	statements,
	subscription,
	verification,
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
	"date_of_birth",
	"guardian_name",
	"emergency_contact_name",
	"emergency_contact_relation",
	"emergency_contact_phone",
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
PROPERTY_FIELDS = (
	"property_name",
	"abbr",
	"address",
	"city",
	"state",
	"pincode",
	"is_active",
	"show_on_listing",
	"listing_for",
	"food_included",
	"map_link",
	"description",
	"amenities",
	"serves_breakfast",
	"breakfast_time",
	"serves_lunch",
	"lunch_time",
	"serves_dinner",
	"dinner_time",
	"meal_skip_cutoff_hours",
	"curfew_time",
	"visitors_until",
	"owner_name",
	"owner_pan",
	"owner_address",
	"police_station",
)
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
	"next_due_date",
	"final_amount",
	"late_fee",
	"early_discount",
	"early_discount_offer",
	"early_discount_until",
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
	"""Managers can use every endpoint; staff logins only those of their areas (access.py)."""
	access.check_access()


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
		"new_leads": frappe.db.count(leads.LEAD, {"status": "New"}) if can("leads") else 0,
		"leave_requests": frappe.db.count(register.LEAVE, {"status": "Requested"}) if can("register") else 0,
		"access": staff_boot(),
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


def can(area) -> bool:
	"""Whether this login can use an area (managers can use all)."""
	staff = access.staff_access()
	return staff is None or area in staff.areas


def staff_boot() -> dict | None:
	staff = access.staff_access()
	if staff is None:
		return None
	return {"areas": sorted(staff.areas), "building": staff.building, "staff_name": staff.staff_name}


@frappe.whitelist()
def get_staff_home(property=None):
	"""A staff login's home page: what needs doing today, in their areas."""
	check_access()
	staff = access.staff_access()
	areas = staff.areas if staff else set(access.AREAS)
	base = {"property": property} if property else {}
	home = {}
	if "register" in areas:
		home["register"] = {
			"leave_requests": frappe.db.count(register.LEAVE, {**base, "status": "Requested"}),
			"visitors_inside": frappe.db.count(register.VISITOR, {**base, "status": "Inside"}),
			"attendance_taken": bool(
				frappe.db.exists(register.ATTENDANCE, {**base, "date": nowdate()})
				if property
				else frappe.db.count(register.ATTENDANCE, {"date": nowdate()})
			),
		}
	if "requests" in areas:
		home["requests"] = frappe.get_all(
			"Maintenance Request",
			filters={**base, "status": ("in", ("Open", "In Progress"))},
			fields=["name", "subject", "room", "priority", "status", "creation"],
			order_by="creation desc",
			limit=5,
		)
	if "payments" in areas:
		home["payments_to_confirm"] = frappe.db.count("Rent Payment", {**base, "docstatus": 0})
		home["overdue"] = frappe.db.count(
			"Tenant Rent Invoice",
			{**base, "docstatus": 1, "outstanding_amount": (">", 0), "next_due_date": ("<", nowdate())},
		)
	if "leads" in areas:
		home["new_leads"] = frappe.db.count(leads.LEAD, {**base, "status": "New"})
	if "food" in areas and property:
		home["food"] = mess.kitchen_count(property, nowdate()) if mess.meals_of(property) else []
	return home


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
	overdue = [
		inv
		for inv in open_invoices
		if (inv.next_due_date or inv.due_date) and getdate(inv.next_due_date or inv.due_date) < today
	]

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
		"overdue_invoices": pictures.add_tenant_pictures(overdue[:6]),
		"recent_payments": frappe.get_all(
			"Rent Payment",
			filters=by_property({"docstatus": 1}, property),
			fields=PAYMENT_LIST_FIELDS,
			order_by="payment_date desc, creation desc",
			limit=6,
		),
		"moving_out": [
			# a "<=" filter counts an empty date as 0001-01-01, so stays without notice are dropped here
			a
			for a in frappe.get_all(
				"Tenant Space Allotment",
				filters=by_property(
					{"docstatus": 1, "status": "Active", "expected_vacate_date": ("is", "set")}, property
				),
				fields=["name", "tenant", "tenant_name", "room", "bed_no", "expected_vacate_date"],
				order_by="expected_vacate_date asc",
			)
			if getdate(a.expected_vacate_date) <= getdate(add_days(today, 30))
		],
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
	pictures.add_tenant_pictures([o for room in occupants.values() for o in room])

	for room in rooms:
		room_type = room_types.get(room.room_type) or {}
		room.capacity = max(cint(room.capacity), 1)
		room.is_furnished = room_type.get("is_furnished")
		room.has_attached_bathroom = room_type.get("has_attached_bathroom")
		room.occupants = occupants.get(room.name, [])
		room.free_beds = room.capacity - len(room.occupants)
		room.outstanding = sum(o.outstanding for o in room.occupants)
	return rooms


def set_room_items(doc, data):
	if "items" in data:
		doc.set(
			"items",
			[
				pick(row, ("item", "quantity", "replacement_cost", "notes"))
				for row in data["items"] or []
				if row.get("item")
			],
		)


@frappe.whitelist()
def get_room_items(room):
	check_access()
	items = frappe.get_all(
		"Room Item",
		filters={"parent": room, "parenttype": "Tenant Space"},
		fields=["item", "quantity", "replacement_cost", "notes"],
		order_by="idx asc",
	)
	return {
		"items": items,
		"suggestions": [{"item": i, "replacement_cost": c} for i, c in inspections.DEFAULT_ITEMS],
	}


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
		set_room_items(doc, data)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Tenant Space", **pick(data, ROOM_FIELDS)})
		set_room_items(doc, data)
		doc.insert()
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
		"Rent Property",
		fields=["name", "image", "listing_slug", *PROPERTY_FIELDS],
		order_by="is_active desc, creation asc",
	)
	staff = access.staff_access()
	if staff and staff.building:
		properties = [p for p in properties if p.name == staff.building]  # a staff login for one building
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
	pictures.set_picture(doc, data.get("picture"))  # a data URL, "" to remove, or left out
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
			"meal_plan",
			"meal_charge",
			"notice_period_days",
			"rent_increase_percent",
			"next_rent_increase_date",
			"notice_given_on",
			"expected_vacate_date",
			"tenant_name",
			"police_verification",
			"verification_submitted_on",
			"police_station",
			"verification_reference",
			"verified_on",
			"verification_acknowledgement",
			"verification_copy",
			"verification_note",
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
	current = next((a for a in allotments if a.docstatus == 1 and a.status == "Active"), None)
	tenant_data = tenant.as_dict()
	tenant_data.pop("aadhar_card_number", None)  # '*****'; see reveal_aadhaar
	return {
		"tenant": tenant_data,
		"allotments": allotments,
		"invoices": invoices,
		"payments": payments,
		"checkin": checkin.get_status(current.name) if current else None,
		"checklists": {a.name: inspections.checklist_status(a.name) for a in allotments if a.docstatus == 1},
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
	pictures.set_picture(doc, data.get("picture"))  # a data URL, "" to remove, or left out
	return doc.name


@frappe.whitelist(methods=["POST"])
def reveal_aadhaar(name):
	check_access()
	tenant = frappe.get_doc("Tenant", name)
	number = tenant.reveal_aadhar()
	activity.log(
		"Privacy", _("viewed the Aadhaar number of {0}").format(tenant.full_name), tenant, tenant=tenant.name
	)
	return number


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
		pdf.of_print(doc.doctype, doc.name, AGREEMENT_FORMAT),
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
		"pay_now": fees.payable_now(doc),
		"discount_now": fees.discount_available(doc),
		"instalments": fees.schedule(doc),
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
		"tenant_picture": pictures.tenant_pictures([doc.tenant]).get(str(doc.tenant)),
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
	rows = pictures.add_tenant_pictures(
		frappe.get_all(
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
				"refund_upi_id",
				"refund_bank_details",
			],
			order_by="vacate_date desc",
		)
	)
	for row in rows:  # when the tenant was told to expect it (see move_out.py)
		row.refund_due_on = move_out.refund_due_on(row)
	return rows


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


# ---------------------------------------------------------------- bank statements (statements.py)


@frappe.whitelist()
def get_bank_statements():
	check_access()
	return statements.get_statements()


@frappe.whitelist(methods=["POST"])
def upload_bank_statement(filename, content, bank=None):
	check_access()
	frappe.has_permission(statements.STATEMENT, "create", throw=True)
	return statements.upload(filename, content, bank)


@frappe.whitelist()
def get_bank_statement(name):
	check_access()
	return statements.get_statement(name)


@frappe.whitelist(methods=["POST"])
def set_bank_statement_line(name, line, tenant=None, rent_invoice=None, status=None):
	check_access()
	statements.set_line(name, line, tenant, rent_invoice, status)


@frappe.whitelist(methods=["POST"])
def confirm_bank_statement(name, lines):
	check_access()
	return statements.confirm(name, lines)


@frappe.whitelist(methods=["POST"])
def rematch_bank_statement(name):
	check_access()
	statements.rematch(name)


@frappe.whitelist(methods=["POST"])
def delete_bank_statement(name):
	check_access()
	statements.delete(name)


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
	"listing_enabled",
	"booking_token_amount",
	"late_fee_enabled",
	"late_fee_type",
	"late_fee_amount",
	"late_fee_max",
	"late_fee_grace_days",
	"early_discount_enabled",
	"early_discount_type",
	"early_discount_value",
	"early_discount_days",
	"landlord_pan",
	"police_verification_enabled",
	"police_verification_days",
	"owner_summary_enabled",
	"owner_summary_day",
	"owner_summary_phone",
	"owner_summary_email",
	"referrals_enabled",
	"referral_reward",
	"referral_friend_discount",
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
		"receipt_signature": settings.receipt_signature,
		"whatsapp": {
			"available": bool(notifications.get_whatsapp_account()),
			"source": "own" if own_whatsapp else ("plan" if notifications.get_whatsapp_account() else None),
			"in_plan": subscription.has_feature("whatsapp"),
		},
		"email_configured": notifications.email_configured(),
		"webhook_url": frappe.utils.get_url("/api/method/rent_management.rent_collection.razorpay_webhook"),
		"listing_url": leads.listing_url(),
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
	frappe.local.response.filecontent = pdf.of_print(
		subscription.PAYMENT, name, subscription.INVOICE_PRINT_FORMAT
	)
	frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def create_autopay_checkout(plan, billing_cycle, start_later=0):
	check_access()
	return subscription.create_autopay_checkout(plan, billing_cycle, start_later=cint(start_later))


@frappe.whitelist(methods=["POST"])
def verify_autopay(razorpay_payment_id, razorpay_subscription_id, razorpay_signature):
	check_access()
	return subscription.verify_autopay(razorpay_payment_id, razorpay_subscription_id, razorpay_signature)


@frappe.whitelist(methods=["POST"])
def cancel_autopay():
	check_access()
	subscription.cancel_autopay()
	return subscription.get_state()


@frappe.whitelist(methods=["POST"])
def create_subscription_checkout(plan, billing_cycle):
	check_access()
	return subscription.create_checkout(plan, billing_cycle)


@frappe.whitelist(methods=["POST"])
def verify_subscription_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
	check_access()
	return subscription.verify_checkout(razorpay_order_id, razorpay_payment_id, razorpay_signature)


# ---------------------------------------------------------------- leads


@frappe.whitelist()
def get_leads(status=None, property=None):
	check_access()
	return leads.get_leads(status, property)


@frappe.whitelist()
def get_lead(name):
	check_access()
	lead = frappe.get_doc(leads.LEAD, name)
	lead.check_permission("read")
	data = lead.as_dict()
	data.pop("access_key", None)
	data["booking_url"] = None
	if lead.token_status == "Pending":
		slug = frappe.db.get_value("Rent Property", lead.property, "listing_slug")
		data["booking_url"] = frappe.utils.get_url(f"/stay/{slug}?booking={lead.access_key}")
	data["room_types"] = leads.get_room_types(lead.property)
	return data


@frappe.whitelist(methods=["POST"])
def save_lead(data):
	check_access()
	return leads.save_lead(data)


@frappe.whitelist(methods=["POST"])
def record_lead_token(name, amount, mode="Cash", reference=None, paid_on=None):
	check_access()
	leads.record_token(name, amount, mode, reference, paid_on)


@frappe.whitelist(methods=["POST"])
def ask_lead_for_token(name, amount=None):
	"""A booking link to send the lead (WhatsApp): it pays the token by Razorpay or UPI."""
	check_access()
	lead = frappe.get_doc(leads.LEAD, name)
	if lead.token_status == "Paid":
		frappe.throw(_("The token is already paid."))
	amount = flt(amount) or flt(lead.token_amount) or leads.token_amount()
	if amount <= 0:
		frappe.throw(_("Enter the token amount."))
	if not lead.room_type and not lead.room:
		frappe.throw(_("Choose the room type the bed is held in first."))
	if flt(lead.token_amount) != amount and lead.payment_link_id:
		lead.payment_link_id = lead.payment_link_url = None  # a new link for the new amount
	lead.update({"token_amount": amount, "token_status": "Pending"})
	lead.save()
	slug = frappe.db.get_value("Rent Property", lead.property, "listing_slug")
	return frappe.utils.get_url(f"/stay/{slug}?booking={lead.access_key}")


@frappe.whitelist(methods=["POST"])
def move_in_lead(
	name, room, allotment_date=None, bed_no=None, rent_amount=None, security_deposit=None, deposit_collected=0
):
	check_access()
	return leads.move_in(
		name, room, allotment_date, bed_no, rent_amount, security_deposit, cint(deposit_collected)
	)


# ---------------------------------------------------------------- check-in


@frappe.whitelist(methods=["POST"])
def send_checkin(allotment):
	check_access()
	return checkin.send_checkin(allotment)


@frappe.whitelist()
def download_verification_form(allotment):
	check_access()
	doc = frappe.get_doc("Tenant Space Allotment", allotment)
	doc.check_permission("print")
	send_pdf(
		f"Police-Verification-{doc.tenant_name or doc.tenant}",
		pdf.of_print(doc.doctype, doc.name, checkin.VERIFICATION_FORMAT),
	)


# ---------------------------------------------------------------- room checklists


@frappe.whitelist()
def get_room_inspection(allotment, inspection_type):
	check_access()
	return inspections.get_inspection(allotment, inspection_type)


@frappe.whitelist(methods=["POST"])
def save_room_inspection(data):
	check_access()
	return inspections.save_inspection(data)


@frappe.whitelist()
def get_checklist_deductions(allotment):
	check_access()
	return {
		"deductions": inspections.settlement_deductions(allotment),
		"move_out": inspections.checklist_status(allotment)["Move-out"],
	}


# ---------------------------------------------------------------- food


@frappe.whitelist()
def get_food(day=None, property=None):
	"""The Food page: what each kitchen cooks today (or another day), the menu and the costs."""
	check_access()
	day = getdate(day or nowdate())
	filters = {"is_active": 1, "food_included": 1}
	if property:
		filters["name"] = property
	buildings = []
	for name in frappe.get_all("Rent Property", filters=filters, pluck="name", order_by="creation asc"):
		buildings.append(
			{
				"name": name,
				"meals": mess.kitchen_count(name, day),
				"menu": mess.get_menu(name),
				"today": mess.menu_for(name, day),
				"costs": mess.food_costs(name, day),
				"cutoff_hours": frappe.db.get_value("Rent Property", name, "meal_skip_cutoff_hours"),
			}
		)
	return {"day": str(day), "weekday": mess.DAYS[day.weekday()], "buildings": buildings}


@frappe.whitelist(methods=["POST"])
def save_menu(property, menu):
	check_access()
	mess.save_menu(property, menu)


@frappe.whitelist(methods=["POST"])
def set_meal_plan(allotment, meal_plan=None, meal_charge=0):
	check_access()
	doc = frappe.get_doc("Tenant Space Allotment", allotment)
	doc.check_permission("write")
	doc.meal_plan = meal_plan or ""
	doc.meal_charge = flt(meal_charge)
	doc.save()


@frappe.whitelist(methods=["POST"])
def skip_meal_for(allotment, date, meal, skip=1):
	"""A manager marks a meal skipped for a tenant (any time, e.g. they called)."""
	check_access()
	mess.set_skip(allotment, date, meal, cint(skip), source="Manager")


# ---------------------------------------------------------------- register


def register_buildings(property=None) -> list[str]:
	filters = {"is_active": 1}
	if property:
		filters["name"] = property
	return frappe.get_all("Rent Property", filters=filters, pluck="name", order_by="creation asc")


@frappe.whitelist()
def get_register(property=None, day=None):
	"""The Register page: tonight's attendance per building, leave and visitors."""
	check_access()
	return {
		"buildings": [
			register.get_attendance(name, day) | {"name": name} for name in register_buildings(property)
		],
		"leaves": register.get_leaves(property),
		"visitors": register.get_visitors(property),
	}


@frappe.whitelist(methods=["POST"])
def save_attendance(property, date, entries):
	check_access()
	return register.save_attendance(property, date, entries)


@frappe.whitelist(methods=["POST"])
def add_leave(allotment, from_date, to_date, destination=None, reason=None):
	check_access()
	return register.request_leave(allotment, from_date, to_date, destination, reason, source="Manager")


@frappe.whitelist(methods=["POST"])
def decide_leave(name, approve, note=None):
	check_access()
	register.decide_leave(name, approve, note)


@frappe.whitelist(methods=["POST"])
def cancel_leave(name):
	check_access()
	register.cancel_leave(name)


@frappe.whitelist(methods=["POST"])
def visitor_in(data):
	check_access()
	return register.check_in(data)


@frappe.whitelist(methods=["POST"])
def visitor_out(name):
	check_access()
	register.check_out(name)


@frappe.whitelist(methods=["POST"])
def cancel_visitor(name):
	check_access()
	frappe.get_doc(register.VISITOR, name).db_set("status", "Cancelled")


# ---------------------------------------------------------------- staff and salaries

STAFF_FIELDS = ("staff_name", "role", "property", "mobile_no", "monthly_salary", "pay_day", "joining_date",
	"leaving_date", "is_active", "payment_mode", "upi_id", "bank_account_no", "ifsc_code", "address",
	"emergency_contact", "notes")  # fmt: skip


@frappe.whitelist()
def get_staff(property=None):
	check_access()
	return salaries.get_staff(property)


@frappe.whitelist(methods=["POST"])
def save_staff(data):
	check_access()
	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc(salaries.STAFF, data["name"])
		doc.update(pick(data, STAFF_FIELDS))
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": salaries.STAFF, **pick(data, STAFF_FIELDS)}).insert()
	if "picture" in data:
		pictures.set_picture(doc, data["picture"])
	return doc.name


@frappe.whitelist()
def get_salaries(month=None, year=None, property=None):
	check_access()
	return salaries.get_salaries(month, year, property)


@frappe.whitelist(methods=["POST"])
def prepare_salaries(month, year, property=None):
	check_access()
	return salaries.prepare(month, year, property)


@frappe.whitelist(methods=["POST"])
def save_salary_slip(name, data):
	check_access()
	return salaries.save_slip(name, data)


@frappe.whitelist(methods=["POST"])
def pay_salary(name, paid_on=None, mode_of_payment=None, reference_no=None):
	check_access()
	salaries.pay(name, paid_on, mode_of_payment, reference_no)


@frappe.whitelist(methods=["POST"])
def undo_salary_payment(name):
	check_access()
	salaries.undo_payment(name)


@frappe.whitelist(methods=["POST"])
def give_advance(staff, amount, advance_date=None, recover_per_month=None, mode_of_payment="Cash", note=None):
	check_access()
	return salaries.give_advance(staff, amount, advance_date, recover_per_month, mode_of_payment, note)


@frappe.whitelist(methods=["POST"])
def delete_advance(name):
	check_access()
	salaries.delete_advance(name)


# ---------------------------------------------------------------- late fees and instalments


@frappe.whitelist(methods=["POST"])
def waive_late_fee(name, waive=1):
	check_access()
	fees.waive_late_fee(name, waive)


@frappe.whitelist(methods=["POST"])
def split_invoice(name, instalments):
	"""Split an invoice into instalments; an empty list removes them."""
	check_access()
	fees.split(name, instalments)


# ---------------------------------------------------------------- the owner's monthly summary


@frappe.whitelist()
def get_owner_summary(month=None, year=None, property=None):
	check_access()
	summary = owner_summary.build(month, year, property)
	owner = owner_summary.owner_contact()
	text = owner_summary.text(summary)
	number = notifications.whatsapp_number(owner.mobile_no)
	return {
		"summary": summary,
		"text": text,
		"whatsapp_url": f"https://wa.me/{number or ''}?text={quote(text)}",
		"owner": {"mobile_no": owner.mobile_no, "email_id": owner.email_id},
		"can_send": bool(
			(owner.mobile_no and notifications.get_whatsapp_account())
			or (owner.email_id and notifications.email_configured())
		),
		"last_sent": frappe.db.get_value(
			notifications.LOG,
			{"message_type": "Owner Summary", "status": "Sent"},
			["creation", "channel", "recipient"],
			as_dict=True,
			order_by="creation desc",
		),
	}


@frappe.whitelist(methods=["POST"])
def send_owner_summary(month=None, year=None):
	check_access()
	return owner_summary.send(month, year)


# ---------------------------------------------------------------- referrals


@frappe.whitelist()
def get_referrals(property=None):
	check_access()
	return referrals.get_referrals(property)


@frappe.whitelist(methods=["POST"])
def pay_out_referral(name, note=None):
	check_access()
	referrals.pay_out(name, note)


# ---------------------------------------------------------------- notice board


@frappe.whitelist()
def get_notices(property=None):
	check_access()
	return notices.get_notices(property)


@frappe.whitelist(methods=["POST"])
def save_notice(data, publish=0):
	check_access()
	name = notices.save(data)
	if cint(publish):
		notices.publish(name)
	return name


@frappe.whitelist(methods=["POST"])
def publish_notice(name):
	check_access()
	notices.publish(name)


@frappe.whitelist(methods=["POST"])
def take_down_notice(name):
	"""Off the tenants' notice board (not withdraw_notice, which is a tenant's notice to leave)."""
	check_access()
	notices.withdraw(name)


@frappe.whitelist(methods=["POST"])
def delete_notice(name):
	check_access()
	notices.delete(name)


# ---------------------------------------------------------------- staff logins (managers only)


@frappe.whitelist()
def get_staff_access_options():
	check_access()
	return {"areas": [{"value": k, "label": v} for k, v in access.AREAS.items()], "presets": access.PRESETS}


@frappe.whitelist(methods=["POST"])
def give_staff_login(staff, email, areas, all_buildings=0):
	check_access()
	return access.give_login(staff, email, areas, all_buildings)


@frappe.whitelist(methods=["POST"])
def remove_staff_login(staff):
	check_access()
	access.remove_login(staff)


# ---------------------------------------------------------------- cash book


@frappe.whitelist()
def get_cash_book(property=None, from_date=None, to_date=None):
	check_access()
	return cash.get_cash_book(property, from_date, to_date)


@frappe.whitelist(methods=["POST"])
def hand_over_cash(to_user, amount, note=None, handed_on=None):
	check_access()
	return cash.hand_over(to_user, amount, note, handed_on)


@frappe.whitelist(methods=["POST"])
def confirm_cash_handover(name, accept=1):
	check_access()
	cash.confirm(name, accept)


@frappe.whitelist(methods=["POST"])
def cancel_cash_handover(name):
	check_access()
	cash.cancel(name)


# ---------------------------------------------------------------- activity log (managers only)


@frappe.whitelist()
def get_activity(property=None, user=None, category=None, from_date=None, to_date=None):
	check_access()
	return activity.get_activity(property, user, category, from_date, to_date)


# ---------------------------------------------------------------- rent receipts for income tax


@frappe.whitelist()
def get_rent_receipts(tenant, fy=None):
	check_access()
	return receipts.summary(tenant, fy)


@frappe.whitelist()
def download_rent_receipt(tenant, fy, invoice=None):
	check_access()
	receipts.send_pdf(tenant, fy, invoice)


@frappe.whitelist()
def get_tenant_statement(tenant, from_date=None, to_date=None):
	check_access()
	frappe.has_permission("Tenant", "read", tenant, throw=True)
	return ledger.statement(tenant, from_date, to_date) | {"no_dues": ledger.no_dues(tenant)}


@frappe.whitelist()
def download_tenant_statement(tenant, from_date=None, to_date=None):
	check_access()
	frappe.has_permission("Tenant", "read", tenant, throw=True)
	ledger.statement_pdf(tenant, from_date, to_date)


@frappe.whitelist()
def download_no_dues(tenant):
	check_access()
	frappe.has_permission("Tenant", "read", tenant, throw=True)
	ledger.certificate_pdf(tenant)


@frappe.whitelist(methods=["POST"])
def save_receipt_signature(picture=None):
	"""Settings: the landlord's signature on rent receipts (a data URL, or "" to remove it)."""
	check_access()
	settings = frappe.get_single("Rent Management Settings")
	pictures.set_image(settings, "receipt_signature", picture, private=True)
	return frappe.db.get_single_value("Rent Management Settings", "receipt_signature")


# ---------------------------------------------------------------- police verification


@frappe.whitelist()
def get_verifications(property=None):
	check_access()
	return verification.get_verifications(property)


@frappe.whitelist(methods=["POST"])
def update_verification(allotment, data):
	check_access()
	verification.update(allotment, data)


@frappe.whitelist(methods=["POST"])
def track_verification(allotment):
	check_access()
	verification.track(allotment)


# ---------------------------------------------------------------- tenant documents


@frappe.whitelist()
def get_tenant_documents(tenant):
	check_access()
	return {"documents": documents.for_tenant(tenant), "types": documents.TYPES}


@frappe.whitelist(methods=["POST"])
def save_tenant_document(tenant, data):
	check_access()
	frappe.get_doc("Tenant", tenant).check_permission("read")
	return documents.save(tenant, data)


@frappe.whitelist(methods=["POST"])
def delete_tenant_document(tenant, name):
	check_access()
	documents.delete(tenant, name)
