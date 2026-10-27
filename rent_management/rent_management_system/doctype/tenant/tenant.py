# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Verhoeff algorithm tables, used for the Aadhaar checksum
VERHOEFF_D = (
	(0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
	(1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
	(2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
	(3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
	(4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
	(5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
	(6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
	(7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
	(8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
	(9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
VERHOEFF_P = (
	(0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
	(1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
	(5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
	(8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
	(9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
	(4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
	(2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
	(7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


class Tenant(Document):
	def validate(self):
		self.set_full_name()
		self.check_aadhar()
		self.make_private("aadhar_card")
		self.make_private("display_picture")

	def set_full_name(self):
		parts = [self.first_name, self.middle_name, self.last_name]
		self.full_name = " ".join(filter(None, parts)).strip()

	def check_aadhar(self):
		"""Validate a newly entered Aadhaar number. Frappe encrypts the field right after validate
		and keeps only '*' in the table, so only the last 4 digits are stored in the clear."""
		if not self.aadhar_card_number:
			self.aadhar_last4 = None
			return
		if self.is_dummy_password(self.aadhar_card_number):
			return  # unchanged

		aadhar = str(self.aadhar_card_number).replace(" ", "")

		if not aadhar.isdigit() or len(aadhar) != 12:
			frappe.throw(_("Aadhaar Number must be exactly 12 digits."))

		if aadhar[0] in ("0", "1"):
			frappe.throw(_("Invalid Aadhaar: Cannot start with 0 or 1."))

		if not is_valid_verhoeff(aadhar):
			frappe.throw(_("Aadhaar validation failed. The checksum is incorrect."))

		self.aadhar_card_number = aadhar
		self.aadhar_last4 = aadhar[-4:]
		frappe.msgprint(
			msg=_("Aadhaar has been successfully verified against the Verhoeff checksum."),
			title=_("Verification Success"),
			indicator="green",
		)

	def make_private(self, field):
		"""The Aadhaar scan and the tenant's photo must never be reachable at a public /files/ URL."""
		url = self.get(field)
		if not url or not url.startswith("/files/"):
			return
		file = frappe.db.get_value("File", {"file_url": url, "is_private": 0})
		if not file:
			return
		file = frappe.get_doc("File", file)
		file.is_private = 1
		file.flags.ignore_permissions = True
		file.save()
		self.set(field, file.file_url)

	def reveal_aadhar(self) -> str:
		"""The full Aadhaar number, for police verification forms. Every view is logged."""
		self.check_permission("write")
		number = self.get_password("aadhar_card_number", raise_exception=False)
		if not number:
			return ""
		self.add_comment("Info", _("Aadhaar number viewed by {0}").format(frappe.session.user))
		return f"{number[:4]} {number[4:8]} {number[8:]}"


def is_valid_verhoeff(number: str) -> bool:
	c = 0
	for i, digit in enumerate(reversed(number)):
		c = VERHOEFF_D[c][VERHOEFF_P[i % 8][int(digit)]]
	return c == 0
