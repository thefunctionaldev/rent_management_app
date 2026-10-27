# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import hashlib
import hmac
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import api, leads, razorpay
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_rent_collection import FakeLandlordRazorpay


class TestLeads(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(leads.LEAD)
		self.building = frappe.get_doc(
			{"doctype": "Rent Property", "property_name": f"Lead Villa {frappe.generate_hash(length=4)}"}
		).insert()
		self.room = make_room(rent=8000, deposit=16000, capacity=2, property=self.building.name)
		self.room_type = self.room.room_type
		settings = frappe.get_single(leads.SETTINGS)
		settings.update(
			{
				"listing_enabled": 1,
				"booking_token_amount": 2000,
				"upi_id": "villa@okicici",
				"upi_payee_name": "Lead Villa",
				"razorpay_enabled": 0,
			}
		)
		settings.save()
		self.slug = frappe.db.get_value("Rent Property", self.building.name, "listing_slug")

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_guest(self, method, *args, **kwargs):
		frappe.set_user("Guest")
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def enquire(self, **kwargs):
		values = {"building": self.slug, "name": "Rohan Iyer", "mobile_no": "98450 12345", **kwargs}
		return self.as_guest(leads.enquire, **values)

	def free_beds(self):
		listing = self.as_guest(leads.get_listing, self.slug)
		return next(r for r in listing["buildings"][0]["room_types"] if r["type"] == self.room_type)["free"]

	def test_listing_shows_rooms_and_free_beds(self):
		self.assertTrue(self.slug.startswith("lead-villa-"))
		listing = self.as_guest(leads.get_listing, self.slug)
		room_type = listing["buildings"][0]["room_types"][0]
		self.assertEqual((room_type["rent"], room_type["deposit"], room_type["free"]), (8000, 16000, 2))
		self.assertEqual(listing["token"], 2000)

		make_allotment(room=self.room)
		self.assertEqual(self.free_beds(), 1)
		self.assertIn(self.slug, [b["slug"] for b in self.as_guest(leads.get_listing)["buildings"]])

		frappe.db.set_single_value(leads.SETTINGS, "listing_enabled", 0)
		self.assertRaises(frappe.PageDoesNotExistError, self.as_guest, leads.get_listing, self.slug)

	def test_enquiry_and_visit(self):
		visit = f"{add_days(nowdate(), 2)} 11:00:00"
		result = self.enquire(room_type=self.room_type, visit_on=visit, email_id="Rohan@Example.com")
		self.assertFalse(result["booking"])
		lead = frappe.get_doc(leads.LEAD, {"access_key": result["key"]})
		self.assertEqual(
			(lead.status, lead.source, lead.mobile_no, lead.email_id),
			("Visit Scheduled", "Listing", "9845012345", "rohan@example.com"),
		)
		booking = self.as_guest(leads.get_booking, result["key"])
		self.assertEqual((booking["name"], booking["token_status"]), ("Rohan", None))
		self.assertNotIn("mobile_no", booking)  # nothing more than the visitor already knows

		self.assertRaises(frappe.ValidationError, self.enquire, room_type="Not a room type")
		self.assertRaises(frappe.ValidationError, self.enquire, move_in_date=add_days(nowdate(), -1))
		self.assertRaises(frappe.ValidationError, self.enquire, mobile_no="123")
		# bots filling the hidden field get a fake answer and no lead
		before = frappe.db.count(leads.LEAD)
		self.enquire(website="http://spam.example")
		self.assertEqual(frappe.db.count(leads.LEAD), before)

	def test_booking_by_upi(self):
		result = self.enquire(room_type=self.room_type, book=1)
		self.assertTrue(result["booking"])
		booking = self.as_guest(leads.get_booking, result["key"])
		self.assertEqual((booking["token_status"], booking["token_amount"]), ("Pending", 2000))
		self.assertIn("am=2000.00", booking["upi_link"])
		self.assertTrue(booking["upi_qr"].startswith("data:image/svg+xml"))
		self.assertFalse(booking["online"])

		booking = self.as_guest(leads.report_token, result["key"], "412345678901")
		self.assertEqual(booking["token_status"], "Reported")
		lead = frappe.db.get_value(leads.LEAD, {"access_key": result["key"]})
		api.record_lead_token(lead, 2000, "UPI", "412345678901")
		self.assertEqual(
			frappe.db.get_value(leads.LEAD, lead, ["status", "token_status"]), ("Booked", "Paid")
		)
		self.assertEqual(self.free_beds(), 1)  # the booked bed is held

	def test_booking_online_and_webhook(self):
		gateway = FakeLandlordRazorpay()
		for name in ("create_payment_link", "get_payment_link"):
			self.enterContext(patch.object(razorpay, name, getattr(gateway, name)))
		frappe.db.set_single_value(leads.SETTINGS, "razorpay_enabled", 1)
		settings = frappe.get_single(leads.SETTINGS)
		settings.update({"razorpay_key_id": "rzp_test_landlord", "razorpay_key_secret": "landlord-secret",
			"razorpay_webhook_secret": "landlord-webhook"})  # fmt: skip
		settings.save()

		key = self.enquire(room_type=self.room_type, book=1)["key"]
		url = self.as_guest(leads.pay_token, key)
		link_id = next(iter(gateway.links))
		self.assertEqual(url, gateway.links[link_id]["short_url"])
		self.assertEqual(gateway.links[link_id]["amount"], 200000)
		self.assertIn(f"booking={key}", gateway.links[link_id]["callback_url"])
		self.assertEqual(self.as_guest(leads.pay_token, key), url)  # one link per booking

		# paid: the return page sees it
		gateway.pay(link_id)
		self.assertEqual(self.as_guest(leads.get_booking, key)["token_status"], "Paid")
		lead = frappe.get_doc(leads.LEAD, {"access_key": key})
		self.assertEqual((lead.status, lead.token_mode), ("Booked", "Razorpay"))

		# the webhook for the same payment changes nothing
		event = {
			"event": "payment_link.paid",
			"payload": {
				"payment_link": {"entity": {"id": link_id}},
				"payment": {"entity": {"id": lead.token_reference, "amount": 200000}},
			},
		}
		body = json.dumps(event)
		signature = hmac.new(b"landlord-webhook", body.encode(), hashlib.sha256).hexdigest()
		with (
			patch.object(frappe, "request", frappe._dict(get_data=lambda: body.encode()), create=True),
			patch.object(frappe, "get_request_header", lambda name, default=None: signature),
		):
			from rent_management import rent_collection

			self.assertEqual(self.as_guest(rent_collection.razorpay_webhook)["status"], "ok")
		self.assertFalse(leads.record_token_payment(lead, lead.token_reference, 2000))

	def test_full_room_takes_enquiries_only(self):
		make_allotment(room=self.room)
		make_allotment(room=self.room)
		self.assertRaises(frappe.ValidationError, self.enquire, room_type=self.room_type, book=1)
		self.assertFalse(self.enquire(room_type=self.room_type)["booking"])

	def test_move_in_counts_the_token(self):
		name = api.save_lead(
			{
				"lead_name": "Meera Hegde",
				"mobile_no": "9876543210",
				"property": self.building.name,
				"room_type": self.room_type,
				"email_id": "meera@example.com",
			}
		)
		self.assertEqual(frappe.db.get_value(leads.LEAD, name, "source"), "Walk-in")
		api.record_lead_token(name, 2000, "Cash")
		result = api.move_in_lead(name, self.room.name, allotment_date=nowdate())
		self.assertTrue(result["payments"])

		tenant = frappe.get_doc("Tenant", result["tenant"])
		self.assertEqual(
			(tenant.first_name, tenant.last_name, tenant.mobile_no), ("Meera", "Hegde", "9876543210")
		)
		allotment = frappe.get_doc("Tenant Space Allotment", result["allotment"])
		self.assertEqual((allotment.room, allotment.docstatus), (self.room.name, 1))
		payments = [frappe.get_doc("Rent Payment", p) for p in result["payments"]]
		self.assertEqual(sum(p.amount for p in payments), 2000)  # all of it, also after a short month
		self.assertEqual({(p.mode_of_payment, p.docstatus) for p in payments}, {("Cash", 1)})
		invoice = frappe.get_doc("Tenant Rent Invoice", payments[0].rent_invoice)
		self.assertEqual(invoice.tenant_space_allotment, allotment.name)
		if len(payments) > 1:  # moved in late in the month: the first invoice is paid in full
			self.assertEqual(invoice.outstanding_amount, 0)

		lead = frappe.get_doc(leads.LEAD, name)
		self.assertEqual((lead.status, str(lead.tenant)), ("Moved In", str(tenant.name)))
		self.assertRaises(frappe.ValidationError, api.move_in_lead, name, self.room.name)

	def test_page_preview(self):
		from rent_management.www import stay

		self.building.db_set("description", 'Near the metro <script>alert("x")</script>')
		with patch.object(frappe, "form_dict", frappe._dict(building=self.slug)):
			context = stay.get_context(frappe._dict())
		self.assertIn(self.building.property_name, context.meta_title)
		self.assertNotIn("<script", context.meta_description)
		self.assertTrue(context.meta_url.endswith(f"/stay/{self.slug}"))
		with patch.object(frappe, "form_dict", frappe._dict(building="no-such-building")):
			self.assertRaises(frappe.PageDoesNotExistError, stay.get_context, frappe._dict())
