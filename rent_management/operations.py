"""Manager setup progress and a conservative, read-only occupancy timeline."""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from rent_management import access


def manager_only():
	if not access.is_manager():
		frappe.throw(_("Only managers can use this page."), frappe.PermissionError)


def setup_status():
	manager_only()
	settings = frappe.get_single("Rent Management Settings")
	counts = {
		key: frappe.db.count(dt)
		for key, dt in (
			("buildings", "Rent Property"),
			("rooms", "Tenant Space"),
			("tenants", "Tenant"),
		)
	}
	return {
		"counts": counts,
		"steps": [
			{"key": "building", "title": "Add your first building", "done": counts["buildings"] > 0},
			{"key": "rooms", "title": "Create rooms and beds", "done": counts["rooms"] > 0},
			{
				"key": "rules",
				"title": "Review rent and payment settings",
				"done": bool(settings.setup_rules_reviewed),
			},
			{"key": "tenant", "title": "Add your first tenant", "done": counts["tenants"] > 0},
			{
				"key": "allotment",
				"title": "Move a tenant into a room",
				"done": bool(frappe.db.count("Tenant Space Allotment", {"docstatus": 1})),
			},
		],
		"settings": {
			k: settings.get(k)
			for k in (
				"rent_due_day",
				"default_notice_days",
				"default_agreement_months",
				"landlord_name",
				"landlord_phone",
				"upi_id",
			)
		},
	}


def calendar(start_date, end_date, property=None):
	manager_only()
	start, end = getdate(start_date), getdate(end_date)
	if end < start or (end - start).days > 61:
		frappe.throw(_("Choose a range of 1 to 62 days."))
	filters = {"property": property} if property else {}
	rooms = frappe.get_all(
		"Tenant Space",
		filters=filters,
		fields=["name", "room_number", "property", "room_type", "capacity", "status"],
		order_by="property, room_number",
	)
	if len(rooms) > 500:
		frappe.throw(_("Select a building with at most 500 rooms."))
	names = [r.name for r in rooms]
	stays = (
		frappe.get_all(
			"Tenant Space Allotment",
			filters={
				"room": ["in", names],
				"docstatus": 1,
				"allotment_date": ["<=", end],
				"status": ["in", ["Active", "Vacated"]],
			},
			fields=[
				"name",
				"room",
				"tenant",
				"tenant_name",
				"bed_no",
				"allotment_date",
				"vacate_date",
				"expected_vacate_date",
				"status",
			],
		)
		if names
		else []
	)
	stays = [s for s in stays if s.status == "Active" or not s.vacate_date or getdate(s.vacate_date) >= start]
	bookings = frappe.get_all(
		"Rent Lead",
		filters={**filters, "status": "Booked"},
		fields=["name", "lead_name", "room", "room_type", "property", "move_in_date"],
		order_by="move_in_date asc",
	)
	return {
		"rooms": rooms,
		"stays": stays,
		"bookings": bookings,
		"today": nowdate(),
		"start_date": str(start),
		"end_date": str(end),
	}
