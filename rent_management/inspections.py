# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Room checklists at move-in and move-out.

Every room has a list of what is in it (Tenant Space > Items, with replacement costs). At
move-in the manager records the condition of each item, with photos; the checklist becomes
part of the rental agreement the tenant signs. At move-out each item is checked against its
move-in condition: damaged and missing items are charged, and those charges are the
deductions offered when the deposit is settled.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from rent_management import pictures

INSPECTION = "Room Inspection"
TYPES = ("Move-in", "Move-out")
ROW_FIELDS = ("item", "quantity", "condition", "move_in_condition", "notes", "replacement_cost", "charge")
DEFAULT_ITEMS = [
	("Bed", 3000),
	("Mattress", 2500),
	("Pillow", 300),
	("Cupboard", 6000),
	("Study table", 2500),
	("Chair", 1200),
	("Ceiling fan", 1800),
	("Tube light", 400),
	("Curtains", 800),
	("Room key", 300),
]


def existing(allotment, inspection_type):
	name = frappe.db.get_value(INSPECTION, {"allotment": allotment, "inspection_type": inspection_type})
	return frappe.get_doc(INSPECTION, name) if name else None


def get_inspection(allotment, inspection_type) -> dict:
	"""The stay's checklist, or a new one to fill in (not saved yet)."""
	if inspection_type not in TYPES:
		frappe.throw(_("Choose a move-in or move-out checklist."))
	stay = frappe.get_doc("Tenant Space Allotment", allotment)
	doc = existing(allotment, inspection_type)
	if doc:
		data = doc.as_dict()
	else:
		data = {
			"name": None,
			"allotment": allotment,
			"inspection_type": inspection_type,
			"inspection_date": nowdate() if inspection_type == "Move-in" else stay.vacate_date or nowdate(),
			"status": "Draft",
			"items": starting_items(stay, inspection_type),
			"notes": None,
		}
	data["tenant_name"] = stay.tenant_name
	data["room"] = stay.room
	data["locked"] = is_locked(stay.name, inspection_type)
	move_in = existing(allotment, "Move-in")
	data["move_in_done"] = bool(move_in and move_in.status == "Completed")
	return data


def starting_items(stay, inspection_type) -> list[dict]:
	room_items = frappe.get_all(
		"Room Item",
		filters={"parent": stay.room, "parenttype": "Tenant Space"},
		fields=["item", "quantity", "replacement_cost", "notes"],
		order_by="idx asc",
	)
	if inspection_type == "Move-out":
		move_in = existing(stay.name, "Move-in")
		if move_in:
			costs = {row.item: row.replacement_cost for row in room_items}
			rows = [
				{
					"item": row.item,
					"quantity": row.quantity,
					"condition": row.condition,  # unchanged unless the manager finds otherwise
					"move_in_condition": row.condition,
					"notes": None,
					"replacement_cost": row.replacement_cost or costs.get(row.item),
					"charge": 0,
				}
				for row in move_in.items
			]
			seen = {row["item"] for row in rows}
			room_items = [row for row in room_items if row.item not in seen]
		else:
			rows = []
	else:
		rows = []
	rows += [
		{
			"item": row.item,
			"quantity": row.quantity or 1,
			"condition": "Good",
			"move_in_condition": None,
			"notes": row.notes,
			"replacement_cost": row.replacement_cost,
			"charge": 0,
		}
		for row in room_items
	]
	return rows


def is_locked(allotment, inspection_type) -> bool:
	if inspection_type == "Move-in":
		return bool(frappe.db.exists("Tenant Check-in", {"allotment": allotment, "status": "Signed"}))
	return bool(
		frappe.db.exists("Security Deposit Settlement", {"tenant_space_allotment": allotment, "docstatus": 1})
	)


def save_inspection(data) -> str:
	"""Save a checklist. Rows may carry `photo_upload` (a data URL) for a new photo."""
	data = frappe.parse_json(data)
	doc = existing(data["allotment"], data["inspection_type"]) or frappe.new_doc(INSPECTION)
	doc.update(
		{
			"allotment": data["allotment"],
			"inspection_type": data["inspection_type"],
			"inspection_date": data.get("inspection_date") or nowdate(),
			"status": "Completed" if cint(data.get("complete")) else data.get("status") or "Draft",
			"notes": data.get("notes"),
		}
	)
	uploads = []
	doc.set("items", [])
	for row in data.get("items") or []:
		if not (row.get("item") or "").strip():
			continue
		child = doc.append(
			"items",
			{field: row.get(field) for field in ROW_FIELDS} | {"photo": row.get("photo") or None},
		)
		if (row.get("photo_upload") or "").startswith("data:"):
			uploads.append((child, row["photo_upload"]))
	doc.save()
	for child, upload in uploads:
		url = pictures.save_file(doc, "items", True, upload)
		frappe.db.set_value("Room Inspection Item", child.name, "photo", url, update_modified=False)
	return doc.name


def settlement_deductions(allotment) -> list[dict]:
	"""What the move-out checklist charges, as deposit deductions."""
	doc = existing(allotment, "Move-out")
	if not doc or doc.status != "Completed":
		return []
	rows = []
	for row in doc.items:
		if not flt(row.charge):
			continue
		key = "key" in (row.item or "").lower()
		rows.append(
			{
				"reason": "Lost Keys" if key and row.condition == "Missing" else "Damages",
				"description": f"{row.item}: {row.condition.lower()}{f' ({row.notes})' if row.notes else ''}"[
					:140
				],
				"amount": flt(row.charge),
				"from_checklist": 1,
			}
		)
	return rows


def move_in_items(allotment) -> list:
	"""The completed move-in checklist, for the rental agreement."""
	doc = existing(allotment, "Move-in") if allotment else None
	if not doc or doc.status != "Completed":
		return []
	return [
		{"item": r.item, "quantity": r.quantity, "condition": r.condition, "notes": r.notes}
		for r in doc.items
	]


def checklist_status(allotment) -> dict:
	return {
		t: frappe.db.get_value(
			INSPECTION,
			{"allotment": allotment, "inspection_type": t},
			["name", "status", "total_charges"],
			as_dict=True,
		)
		for t in TYPES
	}
