# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PropertyExpense(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be more than zero."))
		if not self.is_new() and self.from_salaries():
			before = self.get_doc_before_save()
			if before and (flt(before.amount) != flt(self.amount) or before.property != self.property):
				frappe.throw(_("This is a salary payment. Change it on the Staff page."))

	def from_salaries(self) -> bool:
		return bool(
			frappe.db.exists("Salary Slip", {"expense": self.name})
			or frappe.db.exists("Staff Advance", {"expense": self.name})
		)
