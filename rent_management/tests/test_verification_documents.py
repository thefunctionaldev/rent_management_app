# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import base64

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import api, documents, portal, verification
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)
from rent_management.tests.test_pictures import data_url


def make_pdf() -> str:
	import io

	from pypdf import PdfWriter

	writer, out = PdfWriter(), io.BytesIO()
	writer.add_blank_page(width=200, height=200)
	writer.write(out)
	return "data:application/pdf;base64," + base64.b64encode(out.getvalue()).decode()


PDF = make_pdf()
BROKEN_PDF = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4\n% not really a pdf\n").decode()
SETTINGS = "Rent Management Settings"


def tracking(on=1, days=7):
	frappe.db.set_single_value(
		SETTINGS, {"police_verification_enabled": on, "police_verification_days": days}
	)


class TestPoliceVerification(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		tracking()
		self.building = make_property()
		frappe.db.set_value("Rent Property", self.building, "police_station", "Koramangala PS")
		self.stay = make_allotment(
			room=make_room(rent=7000, property=self.building), allotment_date=nowdate()
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		tracking(0)

	def stay_doc(self):
		return frappe.get_doc("Tenant Space Allotment", self.stay.name)

	def find(self, group):
		return next(
			(r for r in api.get_verifications(self.building)[group] if r.name == self.stay.name), None
		)

	def test_new_stay_to_submit_and_verify(self):
		self.assertEqual(
			(self.stay_doc().police_verification, self.stay_doc().police_station),
			("Pending", "Koramangala PS"),
		)
		self.assertTrue(self.find("pending"))
		frappe.db.set_value(
			"Tenant Space Allotment", self.stay.name, "allotment_date", add_days(nowdate(), -10)
		)
		self.assertEqual(self.find("overdue").days_overdue, 3)

		self.assertRaises(frappe.ValidationError, api.update_verification, self.stay.name, {"status": "Sent"})
		self.assertRaises(frappe.ValidationError, api.update_verification, self.stay.name,
			{"status": "Submitted", "submitted_on": add_days(nowdate(), 2)})  # fmt: skip
		api.update_verification(
			self.stay.name,
			{"status": "Submitted", "reference": "KPS/2026/118", "acknowledgement": data_url("white")},
		)
		doc = self.stay_doc()
		self.assertEqual((doc.police_verification, doc.verification_reference), ("Submitted", "KPS/2026/118"))
		self.assertTrue(doc.verification_acknowledgement.startswith("/private/files/"))
		self.assertTrue(self.find("submitted"))

		api.update_verification(self.stay.name, {"status": "Verified", "copy": PDF})
		doc = self.stay_doc()
		self.assertEqual((doc.police_verification, str(doc.verified_on)), ("Verified", nowdate()))
		self.assertTrue(doc.verification_copy.endswith(".pdf"))
		self.assertTrue(frappe.db.exists("Rent Activity", {"summary": ("like", "%the police verified%")}))

	def test_tracking_off_and_old_stays(self):
		tracking(0)
		old = make_allotment(room=make_room(rent=5000, property=self.building), allotment_date=nowdate())
		self.assertFalse(frappe.db.get_value("Tenant Space Allotment", old.name, "police_verification"))
		self.assertGreaterEqual(api.get_verifications(self.building)["untracked"], 1)
		api.track_verification(old.name)
		self.assertEqual(
			frappe.db.get_value("Tenant Space Allotment", old.name, "police_verification"), "Pending"
		)

	def test_reminder_on_the_due_day(self):
		staff = api.save_staff(
			{"staff_name": "Gopal", "role": "Warden", "property": self.building, "monthly_salary": 9000}
		)
		warden = f"gopal.{frappe.generate_hash(length=5)}@staff.example"
		api.give_staff_login(staff, warden, ["rooms"])
		frappe.db.set_value(
			"Tenant Space Allotment", self.stay.name, "allotment_date", add_days(nowdate(), -7)
		)
		verification.remind()
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"for_user": warden, "subject": ("like", "Police verification due%")}
			)
		)


class TestTenantDocuments(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		email = f"arjun.{frappe.generate_hash(length=5)}@tenant.example"
		self.tenant = frappe.get_doc({"doctype": "Tenant", "first_name": "Arjun", "email_id": email}).insert()
		make_allotment(room=make_room(rent=6000), tenant=self.tenant, allotment_date=nowdate())

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_tenant(self, method, *args):
		frappe.set_user(self.user)
		try:
			return method(*args)
		finally:
			frappe.set_user("Administrator")

	def test_manager_documents(self):
		pan = api.save_tenant_document(
			self.tenant.name,
			{"document_type": "PAN Card", "document_number": "ABCDE1234F", "upload": data_url("red")},
		)
		api.save_tenant_document(
			self.tenant.name,
			{
				"document_type": "Aadhaar Card",
				"document_number": "2341 2341 2346",
				"upload": data_url("white"),
			},
		)
		api.save_tenant_document(
			self.tenant.name, {"document_type": "Visa", "expires_on": add_days(nowdate(), 20), "upload": PDF}
		)
		self.assertRaises(
			frappe.ValidationError, api.save_tenant_document, self.tenant.name, {"document_type": "Passport"}
		)  # no file
		self.assertRaises(frappe.ValidationError, api.save_tenant_document, self.tenant.name,
			{"document_type": "Other", "upload": "data:text/plain;base64," + base64.b64encode(b"hello").decode()})  # fmt: skip
		self.assertRaises(
			frappe.ValidationError,
			api.save_tenant_document,
			self.tenant.name,
			{"document_type": "Other", "upload": BROKEN_PDF},
		)

		docs = {d["document_type"]: d for d in api.get_tenant_documents(self.tenant.name)["documents"]}
		self.assertTrue(docs["PAN Card"]["file"].startswith("/private/files/"))
		self.assertEqual(docs["Aadhaar Card"]["document_number"], "XXXX XXXX 2346")  # never the whole number
		self.assertTrue(docs["Visa"]["is_pdf"] and docs["Visa"]["expiring"])

		frappe.db.set_value(
			"Tenant", self.tenant.name, {"aadhar_card": docs["PAN Card"]["file"], "aadhar_last4": "2346"}
		)
		self.assertIn("aadhaar", [d["key"] for d in api.get_tenant_documents(self.tenant.name)["documents"]])
		api.delete_tenant_document(self.tenant.name, pan)
		self.assertFalse(frappe.db.exists(documents.DOCUMENT, pan))

	def test_tenant_app(self):
		api.invite_tenant(self.tenant.name)
		self.user = frappe.db.get_value("Tenant", self.tenant.name, "user")
		landlords = api.save_tenant_document(
			self.tenant.name, {"document_type": "Rental Agreement", "upload": PDF}
		)
		data = self.as_tenant(
			portal.save_document,
			{
				"document_type": "College ID",
				"expires_on": add_days(nowdate(), 300),
				"upload": data_url("red"),
			},
		)
		mine = next(d for d in data["documents"] if d["document_type"] == "College ID")
		self.assertEqual(mine["source"], "Tenant App")
		self.assertRaises(
			frappe.PermissionError, self.as_tenant, portal.delete_document, landlords
		)  # not theirs to remove

		self.as_tenant(portal.document_file, mine["key"])
		self.assertTrue(frappe.local.response.filecontent.startswith(b"\x89PNG"))
		other = frappe.get_doc({"doctype": "Tenant", "first_name": "Other"}).insert()
		theirs = api.save_tenant_document(
			other.name, {"document_type": "PAN Card", "upload": data_url("white")}
		)
		self.assertRaises(frappe.PermissionError, self.as_tenant, portal.document_file, theirs)
		self.as_tenant(portal.delete_document, mine["key"])
		self.assertFalse(frappe.db.exists(documents.DOCUMENT, mine["key"]))

	def test_expiry_reminder(self):
		api.save_tenant_document(
			self.tenant.name, {"document_type": "Visa", "expires_on": add_days(nowdate(), 30), "upload": PDF}
		)
		from unittest.mock import patch

		with patch("rent_management.subscription.get_manager_users", return_value=["Administrator"]):
			documents.remind_expiring()
		self.assertTrue(
			frappe.db.exists("Notification Log", {"subject": ("like", "%Visa expires in 30 days%")})
		)
