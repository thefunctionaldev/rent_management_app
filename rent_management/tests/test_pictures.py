# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import base64
import io

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from rent_management import api, portal
from rent_management.tests.test_portal import make_portal_tenant


def data_url(color="red", image_format="PNG"):
	buffer = io.BytesIO()
	Image.new("RGB", (40, 40), color).save(buffer, image_format)
	mime = {"PNG": "png", "JPEG": "jpeg"}[image_format]
	return f"data:image/{mime};base64,{base64.b64encode(buffer.getvalue()).decode()}"


class TestPictures(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tenant, self.allotment, _invoice = make_portal_tenant("Asha")

	def tearDown(self):
		frappe.set_user("Administrator")

	def picture(self):
		return frappe.db.get_value("Tenant", self.tenant.name, "display_picture")

	def test_tenant_photo_is_private_and_replaced(self):
		api.save_tenant({"name": self.tenant.name, "first_name": "Asha", "picture": data_url()})
		first = self.picture()
		self.assertTrue(first.startswith("/private/files/"), first)
		self.assertTrue(frappe.db.exists("File", {"file_url": first, "attached_to_name": self.tenant.name}))

		# saving without "picture" keeps it; a new one replaces the old file
		api.save_tenant({"name": self.tenant.name, "first_name": "Asha", "mobile_no": "9876543210"})
		self.assertEqual(self.picture(), first)
		api.save_tenant({"name": self.tenant.name, "first_name": "Asha", "picture": data_url("blue", "JPEG")})
		self.assertNotEqual(self.picture(), first)
		self.assertTrue(self.picture().endswith(".jpg"))
		self.assertFalse(frappe.db.exists("File", {"file_url": first}))

		# shown next to the tenant in room cards
		room = next(r for r in api.get_rooms() if r.name == self.allotment.room)
		self.assertEqual(room.occupants[0].tenant_picture, self.picture())

		api.save_tenant({"name": self.tenant.name, "first_name": "Asha", "picture": ""})
		self.assertIsNone(self.picture())

	def test_only_real_images(self):
		fake = "data:image/png;base64," + base64.b64encode(b"<script>alert(1)</script>").decode()
		for picture in (fake, "data:image/png;base64,not-base64!", "https://example.com/a.png"):
			self.assertRaises(
				frappe.ValidationError,
				api.save_tenant,
				{"name": self.tenant.name, "first_name": "Asha", "picture": picture},
			)
		self.assertIsNone(self.picture())

	def test_building_photo_is_public(self):
		name = api.save_property({"property_name": "Photo Villa", "abbr": "PV", "picture": data_url()})
		image = frappe.db.get_value("Rent Property", name, "image")
		self.assertTrue(image.startswith("/files/"), image)
		self.assertEqual(next(p for p in api.get_properties() if p.name == name).image, image)

	def test_tenant_sets_own_photo(self):
		frappe.set_user(self.tenant.user)
		self.assertIsNone(portal.get_boot()["picture"])
		url = portal.update_picture(data_url())
		self.assertEqual(portal.get_boot()["picture"], url)
		portal.my_picture()
		self.assertTrue(frappe.local.response.filecontent.startswith(b"\x89PNG"))
		self.assertIsNone(portal.update_picture(""))
