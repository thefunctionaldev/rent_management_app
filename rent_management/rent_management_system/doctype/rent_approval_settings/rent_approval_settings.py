import math

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RentApprovalSettings(Document):
	def validate(self):
		seen = set()
		for row in self.rules:
			key = (row.action, row.requester_role)
			if key in seen or not math.isfinite(flt(row.threshold)) or flt(row.threshold) < 0:
				frappe.throw("Use one non-negative threshold per action and requester role.")
			seen.add(key)
		if self.enabled and not self.rules:
			frappe.throw("Add at least one approval rule.")
