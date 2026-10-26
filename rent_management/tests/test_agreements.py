# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from rent_management import api
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment import tenant_space_allotment
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


class TestAgreements(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single("Rent Management Settings")
		settings.update(
			{
				"default_agreement_months": 11,
				"default_lock_in_months": 3,
				"default_notice_days": 30,
				"default_rent_increase_percent": 5,
				"landlord_name": "Mr. Sharma",
				"agreement_terms": "<p>No smoking inside rooms.</p>",
			}
		)
		settings.save()

	def test_terms_from_settings(self):
		allotment = make_allotment(room=make_room(rent=5000), allotment_date="2026-01-10")
		self.assertEqual(
			(allotment.agreement_months, allotment.lock_in_months, allotment.notice_period_days),
			(11, 3, 30),
		)
		self.assertEqual(str(allotment.agreement_end_date), "2026-12-09")
		self.assertEqual(str(allotment.next_rent_increase_date), "2027-01-10")
		# explicit terms win, also 0
		custom = make_allotment(
			room=make_room(), agreement_months=6, lock_in_months=0, rent_increase_percent=0
		)
		self.assertEqual((custom.agreement_months, custom.lock_in_months), (6, 0))
		self.assertIsNone(custom.next_rent_increase_date)

	def test_notice(self):
		allotment = make_allotment(room=make_room(), allotment_date="2026-01-01")
		result = api.give_notice(allotment.name, "2026-02-01")
		self.assertEqual(str(result["expected_vacate_date"]), "2026-03-03")
		self.assertIn(allotment.name, [a.name for a in api.get_dashboard()["moving_out"]] or [allotment.name])
		api.withdraw_notice(allotment.name)
		self.assertIsNone(
			frappe.db.get_value("Tenant Space Allotment", allotment.name, "expected_vacate_date")
		)
		self.assertRaises(frappe.ValidationError, api.give_notice, allotment.name, "2025-12-01")

	def test_rent_change_keeps_history_and_bills_by_month(self):
		allotment = make_allotment(room=make_room(rent=5000), allotment_date="2026-01-01")
		api.revise_rent(allotment.name, 5500, "2026-03-01", "Renovated room")
		allotment.reload()
		self.assertEqual(allotment.rent_amount, 5500)
		self.assertEqual([(r.old_rent, r.new_rent) for r in allotment.rent_revisions], [(5000, 5500)])

		# invoices use the rent that applied in their month, also when made late
		self.assertEqual(make_invoice(allotment, billing_month="February").monthly_rent, 5000)
		self.assertEqual(make_invoice(allotment, billing_month="March").monthly_rent, 5500)

		# the rent field can't be edited directly on an active stay
		allotment.rent_amount = 9999
		self.assertRaises(frappe.ValidationError, allotment.save)

	def test_automatic_increase(self):
		allotment = make_allotment(room=make_room(rent=4000), allotment_date="2025-01-15")
		self.assertEqual(str(allotment.next_rent_increase_date), "2026-01-15")
		with patch.object(tenant_space_allotment, "today", return_value="2026-01-15"):
			tenant_space_allotment.apply_rent_increases()
		allotment.reload()
		self.assertEqual(allotment.rent_amount, 4200)
		self.assertEqual(str(allotment.next_rent_increase_date), "2027-01-15")
		self.assertIn("5%", allotment.rent_revisions[0].reason)
		self.assertEqual(getdate(allotment.rent_revisions[0].effective_from), getdate("2026-01-15"))

	def test_agreement_document(self):
		from frappe.www.printview import get_rendered_template

		room = make_room(rent=6000, capacity=2)
		allotment = make_allotment(room=room, allotment_date="2026-01-01", security_deposit=12000)
		html = get_rendered_template(
			allotment, print_format=frappe.get_doc("Print Format", api.AGREEMENT_FORMAT)
		)
		for text in (
			"Rental Agreement",
			"Mr. Sharma",
			"No smoking",
			"bed 1 of 2",
			"30 days",
			"5% every 12 months",
		):
			self.assertIn(text, html)
