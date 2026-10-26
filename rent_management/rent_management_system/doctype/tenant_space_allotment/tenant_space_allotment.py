# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, getdate, today

from rent_management.rent_management_system.doctype.tenant_space.tenant_space import (
	get_active_allotments,
	update_room_occupancy,
)


class TenantSpaceAllotment(Document):
	def validate(self):
		# changes after submit (deposit collected...) don't move the tenant, so skip the bed checks
		if self._action != "update_after_submit":
			self.validate_room_is_free()
		self.set_defaults_from_room()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_room_is_free(self):
		room = frappe.db.get_value("Tenant Space", self.room, ["status", "capacity"], as_dict=True)
		if room.status == "Under Renovation":
			frappe.throw(
				_("Room {0} is Under Renovation and cannot be allotted.").format(frappe.bold(self.room))
			)

		capacity = max(cint(room.capacity), 1)
		occupied = get_active_allotments(self.room, exclude=self.name)
		if len(occupied) >= capacity:
			frappe.throw(
				_("Room {0} is full: all {1} bed(s) are allotted ({2}).").format(
					frappe.bold(self.room),
					capacity,
					", ".join(
						frappe.get_desk_link("Tenant Space Allotment", a.name, show_title_with_name=True)
						for a in occupied
					),
				)
			)

		# Tenant is autoincrement-named, so compare names as strings
		if cstr(self.tenant) in [cstr(a.tenant) for a in occupied]:
			frappe.throw(
				_("{0} already stays in room {1}.").format(self.tenant_name or self.tenant, self.room)
			)

		taken = {cint(a.bed_no) for a in occupied}
		if not cint(self.bed_no):
			self.bed_no = next(bed for bed in range(1, capacity + 1) if bed not in taken)
		elif cint(self.bed_no) > capacity:
			frappe.throw(_("Room {0} has only {1} bed(s).").format(self.room, capacity))
		elif cint(self.bed_no) in taken:
			frappe.throw(_("Bed {0} in room {1} is already allotted.").format(self.bed_no, self.room))

	def set_defaults_from_room(self):
		if not self.rent_amount:
			self.rent_amount = frappe.db.get_value("Tenant Space", self.room, "room_rent")

		if not self.security_deposit and self.room_type:
			deposit_applicable, security_deposit = frappe.db.get_value(
				"Tenant Space Type", self.room_type, ["deposit_applicable", "security_deposit"]
			)
			if deposit_applicable:
				self.security_deposit = security_deposit

	def on_submit(self):
		self.db_set("status", "Active")
		update_room_occupancy(self.room)
		frappe.msgprint(
			_("{0} moved into room {1}.").format(self.tenant_name, frappe.bold(self.room)), alert=True
		)

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		update_room_occupancy(self.room)

	@frappe.whitelist()
	def vacate(self, vacate_date=None):
		"""Mark the tenant as moved out and free up their bed."""
		if self.docstatus != 1 or self.status != "Active":
			frappe.throw(_("Only an active allotment can be vacated."))

		vacate_date = getdate(vacate_date or today())
		if vacate_date < getdate(self.allotment_date):
			frappe.throw(_("Vacate Date cannot be before the Allotment Date."))

		self.db_set({"status": "Vacated", "vacate_date": vacate_date})
		update_room_occupancy(self.room)
		frappe.msgprint(
			_("{0} moved out of room {1}.").format(self.tenant_name, frappe.bold(self.room)), alert=True
		)
