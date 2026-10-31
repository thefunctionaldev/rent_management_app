# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, getdate, nowdate

from rent_management import api, checkin, renewals
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)

ALLOTMENT = "Tenant Space Allotment"


class TestRenewals(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# an 11-month agreement ending in about 30 days
		start = add_days(add_months(getdate(nowdate()), -11), 30)
		tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Ravi", "last_name": "Menon",
			"email_id": f"ravi.{frappe.generate_hash(length=5)}@example.com"}).insert()  # fmt: skip
		self.stay = make_allotment(room=make_room(rent=10000), tenant=tenant, allotment_date=start,
			agreement_months=11, rent_increase_percent=5)  # fmt: skip

	def tearDown(self):
		frappe.db.rollback()

	def doc(self):
		return frappe.get_doc(ALLOTMENT, self.stay.name)

	def test_renew(self):
		stay = self.doc()
		self.assertEqual(getdate(stay.agreement_start_date), getdate(stay.allotment_date))
		preview = api.get_renewal(stay.name)
		self.assertEqual(getdate(preview["start"]), add_days(getdate(stay.agreement_end_date), 1))
		self.assertEqual((preview["months"], preview["suggested_rent"]), (11, 10500))

		result = api.renew_agreement(stay.name, 12, 10500)
		stay = self.doc()
		self.assertEqual(getdate(stay.agreement_start_date), getdate(preview["start"]))
		self.assertEqual(
			getdate(stay.agreement_end_date), add_days(add_months(getdate(preview["start"]), 12), -1)
		)
		self.assertEqual((stay.renewals, stay.agreement_months, stay.rent_amount), (1, 12, 10500))
		self.assertEqual(stay.rent_revisions[-1].reason, "Agreement renewed")
		self.assertEqual(getdate(stay.rent_revisions[-1].effective_from), getdate(preview["start"]))

		# sent to sign: straight to the signing step, and the old signature isn't the new one's
		signing = frappe.get_doc("Tenant Check-in", result["signing"]["name"])
		self.assertEqual((signing.purpose, signing.status), ("Renewal", "Details Submitted"))
		self.assertEqual(checkin.get_checkin(signing.access_key)["purpose"], "Renewal")
		self.assertIsNone(renewals.signed_after_renewal(stay))
		html = frappe.get_print(ALLOTMENT, stay.name, print_format="Rent Agreement")
		self.assertIn("renewal 1", html)

		# a second link cancels the first: it would sign the old terms
		again = api.send_renewal_for_signing(stay.name)
		self.assertEqual(frappe.db.get_value("Tenant Check-in", signing.name, "status"), "Cancelled")
		self.assertNotEqual(again["name"], signing.name)

	def test_cannot_renew_after_notice(self):
		self.doc().give_notice(nowdate())
		self.assertRaises(frappe.ValidationError, api.renew_agreement, self.stay.name)

	def test_reminders(self):
		end = getdate(self.doc().agreement_end_date)
		for days, expected in ((30, True), (7, True), (12, False)):
			with (
				patch("rent_management.renewals.nowdate", return_value=str(add_days(end, -days))),
				patch("rent_management.portal.notify_managers") as notify,
			):
				renewals.remind()
			subjects = [c.args[0] for c in notify.call_args_list]
			self.assertEqual(f"Ravi Menon's agreement ends in {days} days" in subjects, expected, days)
