# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashHandover(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the amount handed over."))
		if self.from_user == self.to_user:
			frappe.throw(_("Hand it over to someone else."))
