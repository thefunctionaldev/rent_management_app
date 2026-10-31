# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Finding a tenant by whatever you have: a name, a phone number (with or without +91 and
spaces), an email, a room number, or the UTR of a payment they made."""

import re

import frappe
from frappe.utils import cint

ALLOTMENT = "Tenant Space Allotment"


def digits(text) -> str:
	return re.sub(r"\D", "", text or "")


def matches(text, property=None) -> dict:
	"""{tenant: why} for everyone the text finds."""
	text = (text or "").strip()
	if not text:
		return {}
	found = {}

	def add(names, why):
		for name in names:
			found.setdefault(str(name), why)

	like = f"%{text}%"
	add(frappe.get_all("Tenant", filters={"full_name": ("like", like)}, pluck="name"), "name")
	add(frappe.get_all("Tenant", filters={"email_id": ("like", like)}, pluck="name"), "email")

	number = digits(text)
	if len(number) >= 4:
		number = number[-10:] if len(number) > 10 else number  # +91 98450 12345 -> 9845012345
		spaced = (
			"replace(replace(replace(replace(ifnull(mobile_no, ''), ' ', ''), '-', ''), '+', ''), '(', '')"
		)
		add(frappe.db.sql(f"select name from `tabTenant` where {spaced} like %s", (f"%{number}%",), pluck=True), "phone")  # fmt: skip

	# a room: whoever is staying in it now
	room_filters = {"room_number": text}
	if property:
		room_filters["property"] = property
	rooms = frappe.get_all("Tenant Space", filters=room_filters, pluck="name")
	if rooms:
		add(frappe.get_all(ALLOTMENT, filters={"room": ("in", rooms), "docstatus": 1, "status": "Active"},
			pluck="tenant"), "room")  # fmt: skip

	# a payment's reference (UTR)
	if len(text) >= 6:
		refs = {text, text.lstrip("0")} - {""}
		add(frappe.get_all("Rent Payment", filters={"reference_no": ("in", list(refs)), "docstatus": ("<", 2)},
			pluck="tenant", limit=5), "payment")  # fmt: skip
	return found


def quick(text, property=None, limit=8) -> list[dict]:
	"""The sidebar search: the best few, with their room and why they matched."""
	found = matches(text, property)
	if not found:
		return []
	stays = {
		str(s.tenant): s
		for s in frappe.get_all(
			ALLOTMENT,
			filters={"tenant": ("in", list(found)), "docstatus": 1, "status": "Active"},
			fields=["tenant", "room", "bed_no", "property"],
		)
	}
	tenants = frappe.get_all(
		"Tenant",
		filters={"name": ("in", list(found))},
		fields=["name", "full_name", "mobile_no", "status", "display_picture"],
	)
	order = {"room": 0, "phone": 1, "payment": 2, "name": 3, "email": 4}
	rows = []
	for t in tenants:
		stay = stays.get(str(t.name))
		if property and stay and stay.property != property:
			continue
		room = frappe.db.get_value("Tenant Space", stay.room, "room_number") if stay else None
		rows.append(
			{
				"name": t.name,
				"full_name": t.full_name,
				"mobile_no": t.mobile_no,
				"picture": t.display_picture,
				"room": room,
				"bed_no": cint(stay.bed_no) if stay else None,
				"property": stay.property if stay else None,
				"staying": bool(stay),
				"match": found[str(t.name)],
			}
		)
	rows.sort(key=lambda r: (order[r["match"]], not r["staying"], r["full_name"] or ""))
	return rows[:limit]
