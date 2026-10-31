# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import pdf

PDF = b"%PDF-1.4 test"


class TestPdf(IntegrationTestCase):
	def test_made_with_chrome(self):
		with (
			patch("frappe.utils.pdf.get_chrome_pdf", return_value=PDF) as chrome,
			patch("frappe.utils.pdf.get_pdf") as wkhtmltopdf,
		):
			self.assertEqual(pdf.of_html("<p>Hi</p>", {"page-size": "A4"}), PDF)
		self.assertEqual(chrome.call_args.args[4], "chrome")
		wkhtmltopdf.assert_not_called()

	def test_wkhtmltopdf_when_chrome_cant_start(self):
		with (
			patch("frappe.utils.pdf.get_chrome_pdf", side_effect=Exception("Chromium not available")),
			patch("frappe.utils.pdf.get_pdf", return_value=PDF),
		):
			self.assertEqual(pdf.of_html("<p>Hi</p>"), PDF)

	def test_neither_works(self):
		with (
			patch("frappe.utils.pdf.get_chrome_pdf", side_effect=Exception("Chromium not available")),
			patch("frappe.utils.pdf.get_pdf", side_effect=OSError(86, "Bad CPU type in executable")),
			self.assertRaisesRegex(frappe.ValidationError, "bench setup-chrome"),
		):
			pdf.of_html("<p>Hi</p>")

	def test_print_formats_use_chrome(self):
		for name in ("Rent Agreement", "Tenant Rent Invoice Print Format", "Tenant Verification Form"):
			self.assertEqual(frappe.db.get_value("Print Format", name, "pdf_generator"), "chrome", name)

	def test_no_permission_is_not_retried(self):
		with (
			patch("frappe.get_print", side_effect=frappe.PermissionError) as get_print,
			self.assertRaises(frappe.PermissionError),
		):
			pdf.of_print("Tenant Space Allotment", "x", "Rent Agreement")
		self.assertEqual(get_print.call_count, 1)
