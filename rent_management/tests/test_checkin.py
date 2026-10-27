# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import hashlib
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import api, checkin
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_pictures import data_url

DETAILS = {
	"first_name": "Kavya",
	"last_name": "Nair",
	"gender": "Female",
	"date_of_birth": "2000-04-12",
	"guardian_name": "Suresh Nair",
	"permanent_address": "12 MG Road, Kochi",
	"emergency_contact_name": "Suresh Nair",
	"emergency_contact_phone": "9847000111",
}
AADHAAR = "234123412346"  # passes the Verhoeff check


class TestCheckin(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tenant = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": "Kavya",
				"mobile_no": "9847012345",
				"email_id": "kavya@example.com",
			}
		).insert()
		self.stay = make_allotment(room=make_room(rent=7000), tenant=self.tenant, allotment_date=nowdate())
		self.key = frappe.db.get_value(
			checkin.CHECKIN, api.send_checkin(self.stay.name)["name"], "access_key"
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_guest(self, method, *args, **kwargs):
		frappe.set_user("Guest")
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def fill_in(self, **extra):
		return self.as_guest(
			checkin.save_details,
			self.key,
			{**DETAILS, **extra},
			aadhaar_number=AADHAAR,
			aadhaar_card=data_url("white"),
			photo=data_url("red"),
		)

	def test_link_is_reused_until_done(self):
		again = api.send_checkin(self.stay.name)
		self.assertEqual(frappe.db.get_value(checkin.CHECKIN, again["name"], "access_key"), self.key)
		self.assertIn("/checkin?key=", again["url"])
		self.assertEqual(api.get_tenant(self.tenant.name)["checkin"]["status"], "Sent")

		frappe.db.set_value(checkin.CHECKIN, again["name"], "expires_on", add_days(nowdate(), -1))
		self.assertRaises(frappe.DoesNotExistError, self.as_guest, checkin.get_checkin, self.key)
		self.assertRaises(frappe.DoesNotExistError, self.as_guest, checkin.get_checkin)  # no key at all
		self.assertTrue(api.get_tenant(self.tenant.name)["checkin"]["expired"])
		self.assertNotEqual(api.send_checkin(self.stay.name)["name"], again["name"])  # a fresh one

	def test_details_and_documents(self):
		data = self.as_guest(checkin.get_checkin, self.key)
		self.assertEqual((data["status"], data["agreement"]), ("Sent", None))  # no agreement before details

		missing = {**DETAILS, "guardian_name": ""}
		self.assertRaises(frappe.ValidationError, self.as_guest, checkin.save_details, self.key, missing)
		self.assertRaises(frappe.ValidationError, self.fill_in, date_of_birth=nowdate())

		data = self.fill_in(occupation='<img src=x onerror="alert(1)">Designer')
		self.assertEqual(data["status"], "Details Submitted")
		self.assertIn("Rental Agreement", data["agreement"])
		tenant = frappe.get_doc("Tenant", self.tenant.name)
		self.assertEqual((tenant.guardian_name, tenant.aadhar_last4), ("Suresh Nair", "2346"))
		self.assertEqual(tenant.occupation, "Designer")  # no HTML into the agreement
		self.assertTrue(tenant.aadhar_card.startswith("/private/files/"))
		self.assertTrue(tenant.display_picture.startswith("/private/files/"))
		self.assertTrue(frappe.db.exists("Notification Log", {"subject": ("like", "%check-in details%")}))

	def test_sign_with_a_code(self):
		self.fill_in()
		sent = []
		with (
			patch.object(checkin, "code_channel", return_value=("Email", "ka•••@example.com")),
			patch.object(frappe, "sendmail", lambda **kw: sent.append(kw)),
		):
			self.assertEqual(self.as_guest(checkin.send_code, self.key)["channel"], "Email")
			code = sent[0]["subject"].split()[0]
			self.assertEqual(len(code), 6)

			sign = lambda **kw: self.as_guest(checkin.sign, self.key, **kw)  # noqa: E731
			self.assertRaises(frappe.ValidationError, sign, name="Kavya Nair", agree=0, code=code)
			self.assertRaises(frappe.ValidationError, sign, name="Someone Else", agree=1, code=code)
			wrong = "000000" if code != "000000" else "111111"
			self.assertRaises(frappe.ValidationError, sign, name="Kavya Nair", agree=1, code=wrong)
			self.assertEqual(
				frappe.db.get_value(checkin.CHECKIN, {"access_key": self.key}, "otp_attempts"), 1
			)

			data = sign(name="  kavya   nair ", agree=1, code=code)
		self.assertEqual((data["status"], data["signed_name"]), ("Signed", "Kavya Nair"))
		doc = frappe.get_doc(checkin.CHECKIN, {"access_key": self.key})
		self.assertEqual(doc.otp_channel, "Email")
		self.assertEqual(doc.agreement_hash, hashlib.sha256(doc.agreement_snapshot.encode()).hexdigest())
		self.assertIn("Kavya Nair", doc.agreement_snapshot)
		self.assertIsNone(doc.otp_hash)
		# the agreement now says it was signed electronically, and details are locked
		self.assertIn("Signed electronically", self.as_guest(checkin.get_checkin, self.key)["agreement"])
		self.assertRaises(frappe.ValidationError, self.fill_in)

	def test_too_many_wrong_codes(self):
		self.fill_in()
		with (
			patch.object(checkin, "code_channel", return_value=("Email", "x")),
			patch.object(frappe, "sendmail"),
		):
			self.as_guest(checkin.send_code, self.key)
			frappe.db.set_value(
				checkin.CHECKIN, {"access_key": self.key}, "otp_attempts", checkin.MAX_ATTEMPTS
			)
			self.assertRaises(
				frappe.ValidationError, self.as_guest, checkin.sign, self.key, "Kavya Nair", 1, "123456"
			)

	def test_sign_without_a_code_channel(self):
		self.fill_in()
		with patch.object(checkin, "code_channel", return_value=(None, None)):
			self.assertEqual(self.as_guest(checkin.send_code, self.key)["channel"], None)
			data = self.as_guest(checkin.sign, self.key, "Kavya Nair", 1)
		self.assertEqual(data["status"], "Signed")
		self.assertEqual(
			frappe.db.get_value(checkin.CHECKIN, {"access_key": self.key}, "otp_channel"), "None"
		)
		self.assertEqual(api.get_tenant(self.tenant.name)["checkin"]["status"], "Signed")

	def test_verification_form(self):
		from frappe.www.printview import get_rendered_template

		self.fill_in()
		html = get_rendered_template(
			frappe.get_doc(checkin.ALLOTMENT, self.stay.name),
			print_format=frappe.get_doc("Print Format", checkin.VERIFICATION_FORMAT),
		)
		for text in (
			"Police Verification",
			"Kavya Nair",
			"Suresh Nair",
			"2341 2341 2346",
			"data:image/png;base64",
		):
			self.assertIn(text, html)
		self.assertTrue(
			frappe.db.exists(
				"Comment", {"reference_name": self.tenant.name, "content": ("like", "%verification form%")}
			)
		)

	def test_tenant_app_shows_the_link(self):
		from rent_management import portal

		api.invite_tenant(self.tenant.name)
		user = frappe.db.get_value("Tenant", self.tenant.name, "user")
		frappe.set_user(user)
		self.assertIn(self.key, portal.get_home()["checkin_url"])
