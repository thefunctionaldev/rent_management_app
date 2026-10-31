# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, leads, poster
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_property,
	make_room,
)


class TestPoster(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value(
			"Rent Management Settings", {"listing_enabled": 1, "landlord_phone": "9845012345"}
		)
		self.building = make_property()
		frappe.db.set_value(
			"Rent Property", self.building, {"show_on_listing": 1, "amenities": "WiFi\nLaundry"}
		)
		make_room(rent=8500, property=self.building)

	def tearDown(self):
		frappe.db.rollback()

	def test_poster(self):
		page = poster.html(self.building)
		self.assertIn(frappe.db.get_value("Rent Property", self.building, "property_name"), page)
		self.assertIn("9845012345", page)
		self.assertIn("WiFi", page)
		self.assertIn('viewBox="0 0 ', page)  # the QR code scales instead of being cut off
		self.assertIn(leads.listing_url(self.building).split("://", 1)[-1], page)

		api.download_listing_poster(self.building)
		self.assertEqual(frappe.local.response.filecontent[:4], b"%PDF")

	def test_needs_the_listing(self):
		frappe.db.set_value("Rent Property", self.building, "show_on_listing", 0)
		self.assertRaises(frappe.ValidationError, poster.html, self.building)
		frappe.db.set_value("Rent Property", self.building, "show_on_listing", 1)
		frappe.db.set_single_value("Rent Management Settings", "listing_enabled", 0)
		frappe.clear_document_cache("Rent Management Settings", "Rent Management Settings")
		self.assertRaises(frappe.ValidationError, poster.html, self.building)
