# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class TenantDocument(Document):
	def validate(self):
		self.document_number = (self.document_number or "").strip() or None
		if self.document_type == "Aadhaar Card" and self.document_number:
			# Aadhaar numbers are only kept encrypted, on the tenant: here just the last digits
			digits = re.sub(r"\D", "", self.document_number)
			self.document_number = f"XXXX XXXX {digits[-4:]}" if len(digits) >= 4 else None
		if self.issued_on and self.expires_on and getdate(self.expires_on) < getdate(self.issued_on):
			frappe.throw(_("It can't expire before it was issued."))

	def on_trash(self):
		for name in frappe.get_all(
			"File", filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name}, pluck="name"
		):
			frappe.delete_doc("File", name, ignore_permissions=True)
