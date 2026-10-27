# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class StaffAdvance(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the advance amount."))
		if flt(self.recover_per_month) < 0 or flt(self.recover_per_month) > flt(self.amount):
			frappe.throw(_("The monthly recovery must be between 0 and the advance."))
		if flt(self.recovered) > flt(self.amount) + 0.01 or flt(self.recovered) < -0.01:
			frappe.throw(_("Recovered more than the advance."))
		self.outstanding = flt(flt(self.amount) - flt(self.recovered), 2)
		self.status = "Recovered" if self.outstanding <= 0 else "Open"

	def after_insert(self):
		from rent_management.salaries import advance_expense

		advance_expense(self)

	def on_trash(self):
		if flt(self.recovered) > 0:
			frappe.throw(
				_("Part of this advance was recovered from a salary. Undo that salary payment first.")
			)
		if self.expense:
			expense, self.expense = self.expense, None
			self.db_set("expense", None)
			frappe.delete_doc("Property Expense", expense)
