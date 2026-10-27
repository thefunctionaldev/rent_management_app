# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cstr, nowdate, random_string


class TenantCheckin(Document):
	def validate(self):
		if not self.access_key:
			self.access_key = random_string(32)
		if not self.expires_on:
			self.expires_on = add_days(nowdate(), 14)
		tenant = frappe.db.get_value("Tenant Space Allotment", self.allotment, "tenant")
		if cstr(tenant) != cstr(self.tenant):
			frappe.throw(_("Stay {0} is not {1}'s.").format(self.allotment, self.tenant))
