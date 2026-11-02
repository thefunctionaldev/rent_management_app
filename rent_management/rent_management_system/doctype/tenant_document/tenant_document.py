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
		# Clear this attachment reference before File validates remaining links.
		self.db_set("file", None, update_modified=False)
		for name in frappe.get_all(
			"File", filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name}, pluck="name"
		):
			try:
				frappe.delete_doc("File", name, ignore_permissions=True)
			except frappe.LinkExistsError:
				# A legacy tenant field or another document still uses these bytes.
				# Preserve the file and its private tenant scope rather than breaking that link.
				frappe.db.set_value(
					"File",
					name,
					{
						"attached_to_doctype": "Tenant",
						"attached_to_name": self.tenant,
						"attached_to_field": None,
					},
				)
