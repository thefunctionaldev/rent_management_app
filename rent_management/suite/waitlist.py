import re

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now_datetime

from rent_management import leads
from rent_management.suite.common import area, locked, own_fields, positive, save, scoped, validate_property

DT = "Rent Waitlist"


@frappe.whitelist()
def overview(property=None):
	return frappe.get_all(
		DT, filters=scoped("leads", property), fields=["*"], order_by="creation asc", limit_page_length=500
	)


@frappe.whitelist(methods=["POST"])
def save_entry(data):
	data = frappe.parse_json(data)
	area("leads", data.get("property"))
	doc = locked(DT, data["name"]) if data.get("name") else frappe.new_doc(DT)
	if not doc.is_new():
		area("leads", doc.property)
		if doc.status != "Waiting":
			frappe.throw(_("Withdraw the offer before editing this entry."))
	doc.update(
		own_fields(
			data, ("full_name", "phone", "email", "property", "room_type", "budget", "move_in_date", "notes")
		)
	)
	validate_property(doc.property)
	if len(re.sub(r"\D", "", doc.phone or "")) < 10:
		frappe.throw(_("Enter a valid phone number."))
	doc.budget = positive(doc.budget)
	doc.status = "Waiting"
	return save(doc).name


def matching_rooms(doc):
	free_by_type = {row["type"]: row["free"] for row in leads.get_room_types(doc.property)}
	rooms = frappe.get_all(
		"Tenant Space",
		filters={
			"property": doc.property,
			"status": ["not in", ["Under Renovation", "Reserved"]],
			"room_rent": ["<=", doc.budget],
		},
		fields=["name", "room_number", "room_type", "room_rent", "capacity", "occupied_beds"],
	)
	result = []
	for room in rooms:
		if doc.room_type and room.room_type != doc.room_type:
			continue
		booked = frappe.db.count("Rent Lead", {"room": room.name, "status": "Booked"})
		room.free_beds = min(
			max(int(room.capacity or 1) - int(room.occupied_beds or 0) - booked, 0),
			free_by_type.get(room.room_type, 0),
		)
		if room.free_beds:
			result.append(room)
	return result


@frappe.whitelist()
def matches(name):
	doc = frappe.get_doc(DT, name)
	area("leads", doc.property)
	return matching_rooms(doc)


@frappe.whitelist(methods=["POST"])
def offer(name, room, expires_in_days=2):
	doc = locked(DT, name)
	area("leads", doc.property)
	if doc.status not in ("Waiting", "Offered"):
		frappe.throw(_("This entry is no longer waiting."))
	if not 1 <= int(expires_in_days) <= 14:
		frappe.throw(_("An offer must expire within 1 to 14 days."))
	if room not in [r.name for r in matching_rooms(doc)]:
		frappe.throw(_("The room no longer matches the budget or current availability."))
	doc.offer_room, doc.offer_expires, doc.status = (
		room,
		add_days(now_datetime(), int(expires_in_days)),
		"Offered",
	)
	return save(doc).name


@frappe.whitelist(methods=["POST"])
def act(name, action):
	doc = locked(DT, name)
	area("leads", doc.property)
	if action == "accept":
		if doc.status != "Offered" or get_datetime(doc.offer_expires) <= now_datetime():
			frappe.throw(_("This offer has expired or is no longer open."))
		if doc.offer_room not in [r.name for r in matching_rooms(doc)]:
			frappe.throw(_("Availability changed. Offer another room."))
		lead = frappe.get_doc(
			{
				"doctype": "Rent Lead",
				"lead_name": doc.full_name,
				"mobile_no": doc.phone,
				"email_id": doc.email,
				"property": doc.property,
				"room": doc.offer_room,
				"room_type": doc.room_type
				or frappe.db.get_value("Tenant Space", doc.offer_room, "room_type"),
				"move_in_date": doc.move_in_date,
				"status": "Contacted",
				"source": "Phone",
				"notes": f"Accepted waitlist offer {doc.name}. Complete booking/move-in normally.",
			}
		).insert()
		doc.lead, doc.status = lead.name, "Converted"
	elif action in ("withdraw", "close") and doc.status in ("Waiting", "Offered"):
		doc.status = "Waiting" if action == "withdraw" else "Closed"
		doc.offer_room = doc.offer_expires = None
	else:
		frappe.throw(_("This action is not available."))
	return save(doc).name


def expire():
	for name in frappe.get_all(
		DT, filters={"status": "Offered", "offer_expires": ["<=", now_datetime()]}, pluck="name"
	):
		doc = locked(DT, name)
		if doc.status == "Offered" and get_datetime(doc.offer_expires) <= now_datetime():
			doc.status, doc.offer_room, doc.offer_expires = "Waiting", None, None
			save(doc)
