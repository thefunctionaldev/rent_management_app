# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate


class StaffMember(Document):
	def validate(self):
		self.staff_name = (self.staff_name or "").strip()
		if flt(self.monthly_salary) <= 0:
			frappe.throw(_("Enter the monthly salary."))
		if not 1 <= cint(self.pay_day) <= 28:
			frappe.throw(_("Pay day must be between 1 and 28."))
		if self.leaving_date:
			if getdate(self.leaving_date) < getdate(self.joining_date):
				frappe.throw(_("They can't leave before they join."))
			if getdate(self.leaving_date) <= getdate(nowdate()):
				self.is_active = 0
		if self.ifsc_code:
			self.ifsc_code = self.ifsc_code.strip().upper()
