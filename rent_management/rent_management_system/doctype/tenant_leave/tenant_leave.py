# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class TenantLeave(Document):
	def validate(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("The leave can't end before it starts."))
		if self.status in ("Requested", "Approved"):
			overlap = frappe.db.get_value(
				"Tenant Leave",
				{
					"allotment": self.allotment,
					"status": ("in", ("Requested", "Approved")),
					"from_date": ("<=", self.to_date),
					"to_date": (">=", self.from_date),
					"name": ("!=", self.name),
				},
			)
			if overlap:
				frappe.throw(_("There's already a leave for these days ({0}).").format(overlap))
