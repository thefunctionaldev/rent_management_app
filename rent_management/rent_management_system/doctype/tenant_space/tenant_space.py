# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from rent_management.rent_management_system.doctype.rent_property.rent_property import get_default_property

# statuses set by hand; the rest follow from the allotments
MANUAL_STATUSES = ("Reserved", "Under Renovation")


class TenantSpace(Document):
	def autoname(self):
		# room numbers repeat across buildings: 101 in two buildings becomes 101 and 101-B2
		self.room_number = (self.room_number or "").strip()
		self.property = self.property or get_default_property()
		self.validate_unique_room_number()
		name = self.room_number
		if frappe.db.exists("Tenant Space", name):
			abbr = frappe.db.get_value("Rent Property", self.property, "abbr") or self.property
			name = f"{self.room_number}-{abbr}"
		self.name = name

	def before_validate(self):
		if not self.property:
			self.property = get_default_property()

	def validate(self):
		self.capacity = max(cint(self.capacity), 1)
		self.validate_unique_room_number()
		if not self.is_new():
			occupied = get_active_allotments(self.name)
			if len(occupied) > self.capacity:
				frappe.throw(
					_("Room {0} has {1} tenants, so it needs at least {1} beds.").format(
						self.name, len(occupied)
					)
				)
			beds_in_use = [a.bed_no for a in occupied if cint(a.bed_no) > self.capacity]
			if beds_in_use:
				frappe.throw(_("Bed {0} is occupied. Move that tenant first.").format(max(beds_in_use)))
			self.occupied_beds = len(occupied)
			self.status = get_room_status(self, len(occupied))

	def validate_unique_room_number(self):
		duplicate = frappe.db.get_value(
			"Tenant Space",
			{"property": self.property, "room_number": self.room_number, "name": ("!=", self.name)},
		)
		if duplicate:
			frappe.throw(
				_("Room {0} already exists in {1}.").format(frappe.bold(self.room_number), self.property)
			)


def get_active_allotments(room, exclude=None):
	return frappe.get_all(
		"Tenant Space Allotment",
		filters={
			"room": room,
			"docstatus": 1,
			"status": "Active",
			"name": ("!=", exclude or ""),
		},
		fields=["name", "tenant", "tenant_name", "allotment_date", "bed_no"],
		order_by="bed_no asc, allotment_date asc",
	)


def get_room_status(room, occupied: int) -> str:
	if occupied >= cint(room.capacity or 1):
		return "Occupied"
	if occupied:
		return "Partly Occupied"
	if room.status in MANUAL_STATUSES:
		return room.status
	return "Available"


def update_room_occupancy(room_name: str):
	"""Recompute occupied beds, status and the single-tenant fields of a room from its allotments."""
	room = frappe.db.get_value("Tenant Space", room_name, ["name", "status", "capacity"], as_dict=True)
	if not room:
		return
	active = get_active_allotments(room_name)
	only = active[0] if len(active) == 1 else None
	frappe.db.set_value(
		"Tenant Space",
		room_name,
		{
			"occupied_beds": len(active),
			"status": get_room_status(room, len(active)),
			"tenant": only.tenant if only else None,
			"tenant_name": only.tenant_name
			if only
			else (_("{0} tenants").format(len(active)) if active else None),
			"checkin_date": only.allotment_date if only else None,
			"current_allotment": only.name if only else None,
		},
	)
