# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RoomInspection(Document):
	def validate(self):
		other = frappe.db.exists(
			"Room Inspection",
			{"allotment": self.allotment, "inspection_type": self.inspection_type, "name": ("!=", self.name)},
		)
		if other:
			frappe.throw(
				_("This stay already has a {0} checklist ({1}).").format(self.inspection_type, other)
			)
		self.check_locked()
		if not self.inspected_by:
			self.inspected_by = frappe.session.user
		for row in self.items:
			if self.inspection_type == "Move-in" or row.condition in ("Good", "Fair"):
				row.charge = 0
			elif row.condition == "Missing" and not flt(row.charge):
				row.charge = flt(row.replacement_cost) * max(row.quantity or 1, 1)
		self.total_charges = sum(flt(row.charge) for row in self.items)

	def check_locked(self):
		"""What the tenant signed for, or what their deposit was settled on, stays as it was."""
		if self.is_new():
			return
		if self.inspection_type == "Move-in" and frappe.db.exists(
			"Tenant Check-in", {"allotment": self.allotment, "status": "Signed"}
		):
			frappe.throw(_("The tenant signed their agreement with this checklist, so it can't be changed."))
		if self.inspection_type == "Move-out" and frappe.db.get_value(
			"Security Deposit Settlement", {"tenant_space_allotment": self.allotment, "docstatus": 1}
		):
			frappe.throw(_("The deposit is already settled with this checklist, so it can't be changed."))
