# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management.rent_management_system.doctype.tenant.tenant import (
	VERHOEFF_D,
	VERHOEFF_P,
	is_valid_verhoeff,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def make_aadhaar(first_11: str) -> str:
	"""Append the Verhoeff check digit to an 11 digit number."""
	c = 0
	for i, digit in enumerate(reversed(first_11)):
		c = VERHOEFF_D[c][VERHOEFF_P[(i + 1) % 8][int(digit)]]
	return first_11 + str(VERHOEFF_INV[c])


class IntegrationTestTenant(IntegrationTestCase):
	def test_full_name(self):
		tenant = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Ravi", "middle_name": "", "last_name": "Kumar"}
		).insert()
		self.assertEqual(tenant.full_name, "Ravi Kumar")

	def test_valid_aadhaar(self):
		aadhaar = make_aadhaar("23456789012")
		self.assertTrue(is_valid_verhoeff(aadhaar))
		tenant = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Asha", "aadhar_card_number": f"{aadhaar[:4]} {aadhaar[4:]}"}
		).insert()
		self.assertEqual(tenant.get_password("aadhar_card_number"), aadhaar)
		self.assertEqual(tenant.aadhar_last4, aadhaar[-4:])

	def test_aadhaar_is_encrypted(self):
		aadhaar = make_aadhaar("34567890123")
		tenant = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Enc", "aadhar_card_number": aadhaar}
		).insert()
		# the table holds only asterisks, the number is in the encrypted __Auth store
		self.assertEqual(frappe.db.get_value("Tenant", tenant.name, "aadhar_card_number"), "*" * 12)

		# saving the form again (with the masked value) keeps the number
		tenant.reload()
		tenant.occupation = "Engineer"
		tenant.save()
		self.assertEqual(tenant.get_password("aadhar_card_number"), aadhaar)

		self.assertEqual(tenant.reveal_aadhar(), f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}")
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Tenant",
					"reference_name": tenant.name,
					"content": ("like", "%Aadhaar%viewed%"),
				},
			)
		)

	def test_aadhaar_card_is_private(self):
		tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Scan"}).insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"aadhaar-{tenant.name}.txt",
				"content": b"scan",
				"is_private": 0,
				"attached_to_doctype": "Tenant",
				"attached_to_name": tenant.name,
			}
		).insert()
		tenant.aadhar_card = file.file_url
		tenant.save()
		self.assertTrue(tenant.aadhar_card.startswith("/private/files/"))
		self.assertEqual(frappe.db.get_value("File", file.name, "is_private"), 1)

	def test_encrypt_patch(self):
		from rent_management.patches.v1_3 import encrypt_aadhaar

		aadhaar = make_aadhaar("45678901234")
		tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Old"}).insert()
		frappe.db.set_value("Tenant", tenant.name, "aadhar_card_number", aadhaar)  # as stored before
		encrypt_aadhaar.execute()
		tenant.reload()
		self.assertEqual(tenant.aadhar_card_number, "*" * 12)
		self.assertEqual(tenant.aadhar_last4, aadhaar[-4:])
		self.assertEqual(tenant.get_password("aadhar_card_number"), aadhaar)

	def test_invalid_aadhaar(self):
		valid = make_aadhaar("23456789012")
		wrong_checksum = valid[:-1] + str((int(valid[-1]) + 1) % 10)
		for number in (wrong_checksum, "1" + valid[1:], "12345", "abcdefghijkl"):
			tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "X", "aadhar_card_number": number})
			self.assertRaises(frappe.ValidationError, tenant.insert)
