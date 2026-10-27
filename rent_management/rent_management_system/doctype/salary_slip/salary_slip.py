# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SalarySlip(Document):
	def validate(self):
		from rent_management.salaries import calculate

		existing = frappe.db.get_value(
			"Salary Slip",
			{
				"staff": self.staff,
				"salary_month": self.salary_month,
				"salary_year": self.salary_year,
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(
				_("{0} already has a salary slip for {1} {2}.").format(
					self.staff_name or self.staff, self.salary_month, self.salary_year
				),
				frappe.DuplicateEntryError,
			)
		before = self.get_doc_before_save()
		if before and before.status == "Paid" and not self.flags.paying:
			frappe.throw(_("This salary is paid. Undo the payment to change it."))
		if self.status != "Paid":
			calculate(self)

	def on_trash(self):
		if self.status == "Paid":
			frappe.throw(_("This salary is paid. Undo the payment first."))
