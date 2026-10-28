# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate

from rent_management import api, leads, portal, referrals
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


def settings(**values):
	for field, value in values.items():
		frappe.db.set_single_value(referrals.SETTINGS, field, value)
	frappe.clear_document_cache(referrals.SETTINGS, referrals.SETTINGS)


class TestReferrals(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(leads.LEAD)
		frappe.db.delete(referrals.REFERRAL)
		self.building = frappe.get_doc(
			{"doctype": "Rent Property", "property_name": f"Friends PG {frappe.generate_hash(length=4)}"}
		).insert()
		self.room = make_room(rent=8000, capacity=2, property=self.building.name)
		settings(
			listing_enabled=1,
			booking_token_amount=0,
			referrals_enabled=1,
			referral_reward=1000,
			referral_friend_discount=500,
			late_fee_enabled=0,
			early_discount_enabled=0,
		)
		self.slug = frappe.db.get_value("Rent Property", self.building.name, "listing_slug")
		email = f"asha.{frappe.generate_hash(length=5)}@tenant.example"
		self.asha = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Asha", "mobile_no": "9845011122", "email_id": email}
		).insert()
		self.asha_stay = make_allotment(
			room=make_room(rent=9000, property=self.building.name),
			tenant=self.asha,
			allotment_date="2026-01-01",
		)
		self.code = referrals.code_for(self.asha.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		settings(referrals_enabled=0)

	def as_guest(self, method, *args, **kwargs):
		frappe.set_user("Guest")
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def enquire(self, name="Rohan Iyer", mobile="9876512345", **kwargs):
		key = self.as_guest(
			leads.enquire, building=self.slug, name=name, mobile_no=mobile, ref=self.code.lower(), **kwargs
		)["key"]
		return frappe.get_doc(leads.LEAD, {"access_key": key})

	def friend_moves_in(self):
		lead = self.enquire()
		result = api.move_in_lead(lead.name, self.room.name, allotment_date=nowdate())
		today = getdate(nowdate())
		invoice = make_invoice(
			frappe.get_doc("Tenant Space Allotment", result["allotment"]),
			billing_month=MONTHS[today.month - 1],
			billing_year=today.year,
			posting_date=nowdate(),
			submit=True,
		)
		return lead, invoice

	def pay(self, invoice):
		payment = frappe.get_doc(
			{"doctype": "Rent Payment", "tenant": invoice.tenant, "rent_invoice": invoice.name,
				"amount": invoice.outstanding_amount, "payment_date": nowdate(), "mode_of_payment": "UPI"}
		).insert()  # fmt: skip
		payment.submit()
		return payment

	def referral(self):
		return frappe.get_doc(referrals.REFERRAL, {"referrer": self.asha.name})

	def test_code_and_listing(self):
		self.assertTrue(self.code.startswith("ASHA"))
		self.assertEqual(referrals.code_for(self.asha.name), self.code)  # kept
		listing = self.as_guest(leads.get_listing, self.slug, ref=self.code)
		self.assertEqual(listing["referred_by"], {"name": "Asha", "discount": 500})
		self.assertIsNone(self.as_guest(leads.get_listing, self.slug, ref="NOBODY1")["referred_by"])

	def test_enquiries_through_the_link(self):
		lead = self.enquire()
		self.assertEqual((lead.source, str(lead.referred_by)), ("Referral", str(self.asha.name)))
		self.assertEqual(self.referral().status, "Enquired")
		self.enquire(
			mobile="98760 12345".replace(" ", "") if False else "9876512345"
		)  # the same friend again
		self.assertEqual(frappe.db.count(referrals.REFERRAL), 1)
		self.assertEqual(self.enquire(name="Asha", mobile="+91 98450 11122").source, "Listing")  # herself

		lead.reload()
		lead.status = "Lost"
		lead.save()
		self.assertEqual(self.referral().status, "Not Eligible")

	def test_discount_reward_and_credit(self):
		_lead, invoice = self.friend_moves_in()
		referral = self.referral()
		self.assertEqual(
			(referral.status, referral.friend_discount, referral.reward_amount), ("Moved In", 500, 1000)
		)
		credit = [c for c in invoice.charges if c.charge_type == referrals.CHARGE]
		self.assertEqual([c.amount for c in credit], [-500])
		self.assertEqual(referral.friend_discount_invoice, invoice.name)

		payment = self.pay(invoice)
		self.assertEqual(self.referral().status, "Earned")
		self.assertTrue(
			frappe.db.exists("Notification Log", {"subject": ("like", "Referral reward earned%")})
		)
		payment.cancel()
		self.assertEqual(self.referral().status, "Moved In")
		self.pay(frappe.get_doc("Tenant Rent Invoice", invoice.name))
		self.assertEqual(self.referral().status, "Earned")

		# the reward comes off Asha's next rent
		asha_invoice = make_invoice(self.asha_stay, billing_month="February", posting_date="2026-02-01")
		self.assertEqual(
			[(c.charge_type, c.amount) for c in asha_invoice.charges if c.referral],
			[(referrals.CHARGE, -1000)],
		)
		self.assertEqual(asha_invoice.final_amount, 8000)
		referral = self.referral()
		self.assertEqual(
			(referral.status, referral.reward_mode, referral.reward_invoice),
			("Rewarded", "Rent Credit", asha_invoice.name),
		)
		self.assertEqual(api.get_referrals()["rewarded"], 1000)

		asha_invoice.delete()  # gives the reward back
		self.assertEqual((self.referral().status, self.referral().reward_invoice), ("Earned", None))
		api.pay_out_referral(self.referral().name)
		self.assertEqual((self.referral().status, self.referral().reward_mode), ("Rewarded", "Paid Out"))
		self.assertTrue(frappe.db.exists("Property Expense", {"category": "Marketing", "amount": 1000}))

	def test_credit_never_more_than_the_invoice(self):
		settings(referral_friend_discount=50000)
		_lead, invoice = self.friend_moves_in()
		self.assertFalse([c for c in invoice.charges if c.charge_type == referrals.CHARGE])
		self.assertIsNone(self.referral().friend_discount_invoice)  # still owed, for a bigger invoice

	def test_tenant_app(self):
		api.invite_tenant(self.asha.name)
		frappe.set_user(frappe.db.get_value("Tenant", self.asha.name, "user"))
		self.assertTrue(portal.get_boot()["referrals"])
		data = portal.get_referral()
		self.assertTrue(data["url"].endswith(f"?ref={self.code}"))
		self.assertIn(data["url"], data["text"])
		self.assertEqual((data["reward"], data["friend_discount"]), (1000, 500))
