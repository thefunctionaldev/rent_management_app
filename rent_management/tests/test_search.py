# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, search
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


class TestSearch(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.room_no = "R" + frappe.generate_hash(length=4).upper()
		self.tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Zubin", "last_name": "Wadia",
			"mobile_no": "+91 98450-77123"}).insert()  # fmt: skip
		stay = make_allotment(room=make_room(rent=5000, room_number=self.room_no), tenant=self.tenant,
			allotment_date="2026-01-01")  # fmt: skip
		self.utr = "5" + frappe.generate_hash(length=11).upper()
		api.record_payment(make_invoice(stay, submit=True).name, 2000, "UPI", "2026-01-04", self.utr)

	def tearDown(self):
		frappe.db.rollback()

	def found(self, text):
		return search.matches(text).get(str(self.tenant.name))

	def test_by_everything(self):
		self.assertEqual(self.found("zubin"), "name")
		self.assertEqual(self.found("9845077123"), "phone")
		self.assertEqual(self.found("+91 98450 77123"), "phone")
		self.assertEqual(self.found("77123"), "phone")
		self.assertEqual(self.found(self.room_no), "room")
		self.assertEqual(self.found(self.utr), "payment")
		self.assertEqual(self.found("0000" + self.utr), "payment")
		self.assertIsNone(self.found("nobody-like-this"))

		rows = api.quick_search(self.room_no)
		self.assertEqual(
			(rows[0]["full_name"], rows[0]["room"], rows[0]["match"]), ("Zubin Wadia", self.room_no, "room")
		)
		self.assertIn(str(self.tenant.name), [str(t.name) for t in api.get_tenants(search="98450 77123")])
