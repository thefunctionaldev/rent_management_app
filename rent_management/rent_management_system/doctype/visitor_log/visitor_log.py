# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class VisitorLog(Document):
	def validate(self):
		if self.status == "Expected" and not self.expected_on:
			frappe.throw(_("When is the visitor coming?"))
		if self.check_in and self.check_out and get_datetime(self.check_out) < get_datetime(self.check_in):
			frappe.throw(_("A visitor can't leave before they arrive."))
