# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api, notifications, portal, rent_collection
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_api import make_user


def make_portal_tenant(first_name):
	email = f"{first_name.lower()}.{frappe.generate_hash(length=5)}@tenant.example"
	tenant = frappe.get_doc({"doctype": "Tenant", "first_name": first_name, "email_id": email}).insert()
	allotment = make_allotment(room=make_room(rent=5000), tenant=tenant, allotment_date="2026-01-01")
	invoice = make_invoice(allotment, submit=True)
	api.invite_tenant(tenant.name)
	return frappe.get_doc("Tenant", tenant.name), allotment, invoice


class TestPortal(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tenant, self.allotment, self.invoice = make_portal_tenant("Kiran")
		self.other, _other_allotment, self.other_invoice = make_portal_tenant("Ravi")

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_tenant(self, tenant=None):
		frappe.set_user((tenant or self.tenant).user)

	def test_invite(self):
		user = frappe.get_doc("User", self.tenant.user)
		self.assertEqual(user.user_type, "Website User")
		self.assertIn(portal.TENANT_ROLE, frappe.get_roles(user.name))
		# inviting again reuses the login
		self.assertTrue(api.invite_tenant(self.tenant.name)["link"].startswith("http"))

		# someone else's login can't be reused
		clash = frappe.get_doc(
			{"doctype": "Tenant", "first_name": "Clash", "email_id": self.tenant.email_id}
		).insert()
		self.assertRaises(frappe.ValidationError, api.invite_tenant, clash.name)
		staff = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": "Staff",
				"email_id": make_user("staff.member@example.com", ["Rent Manager"]),
			}
		).insert()
		self.assertRaises(frappe.ValidationError, api.invite_tenant, staff.name)
		no_email = frappe.get_doc({"doctype": "Tenant", "first_name": "NoMail"}).insert()
		self.assertRaises(frappe.ValidationError, api.invite_tenant, no_email.name)

	def test_tenant_sees_only_their_own_data(self):
		self.as_tenant()
		boot = portal.get_boot()
		self.assertEqual(str(boot["tenant"]), str(self.tenant.name))
		home = portal.get_home()
		self.assertEqual(home["due"], 5000)
		self.assertEqual(home["stay"]["name"], self.allotment.name)
		self.assertEqual([i.name for i in portal.get_invoices()], [self.invoice.name])
		self.assertEqual(portal.get_invoice(self.invoice.name)["invoice"]["outstanding_amount"], 5000)

		self.assertRaises(frappe.PermissionError, portal.get_invoice, self.other_invoice.name)
		self.assertRaises(frappe.PermissionError, portal.report_payment, self.other_invoice.name, 100)
		self.assertRaises(frappe.PermissionError, portal.pay_online, self.other_invoice.name)
		# and not the manager API
		self.assertRaises(frappe.PermissionError, api.get_tenants)

	def test_unlinked_user(self):
		frappe.set_user(make_user("not.a.tenant@example.com"))
		self.assertRaises(frappe.PermissionError, portal.get_home)

	def test_reported_payment_is_confirmed_by_manager(self):
		self.as_tenant()
		draft = portal.report_payment(self.invoice.name, 5000, "UTR123456")
		self.assertEqual(frappe.db.get_value("Rent Payment", draft, "docstatus"), 0)
		self.assertEqual(portal.get_home()["pending_confirmation"], 1)

		frappe.set_user("Administrator")
		self.assertIn(draft, [p.name for p in api.get_payments_to_confirm()])
		api.confirm_payment(draft)
		self.assertEqual(frappe.db.get_value("Tenant Rent Invoice", self.invoice.name, "status"), "Paid")

	def test_rejected_payment(self):
		self.as_tenant()
		draft = portal.report_payment(self.invoice.name, 1000, "WRONG")
		frappe.set_user("Administrator")
		api.reject_payment(draft, "Not received")
		self.assertFalse(frappe.db.exists("Rent Payment", draft))

	def test_requests(self):
		self.as_tenant()
		name = portal.create_request("Fan not working", "Electrical", "Since yesterday", "High")
		request = frappe.get_doc("Maintenance Request", name)
		self.assertEqual(
			(str(request.tenant), request.room, request.raised_via),
			(str(self.tenant.name), self.allotment.room, "Tenant App"),
		)
		self.assertEqual([r.name for r in portal.get_requests()], [name])
		self.assertRaises(frappe.ValidationError, portal.create_request, "x", "Not a category")

		frappe.set_user("Administrator")
		with patch.object(notifications, "send", return_value=["Sent"]) as send:
			api.save_request({"name": name, "status": "Resolved", "resolution": "Fan replaced"})
		self.assertTrue(frappe.db.get_value("Maintenance Request", name, "resolved_on"))
		self.assertEqual(send.call_args.args[0], "Request Update")
		self.assertIn("resolved", send.call_args.args[2])

	def test_tenant_gives_notice(self):
		self.as_tenant()
		result = portal.give_notice()
		self.assertTrue(result["expected_vacate_date"])
		self.assertRaises(frappe.ValidationError, portal.give_notice)

	def test_pay_online(self):
		self.as_tenant()
		with patch.object(rent_collection, "get_payment_link", return_value="https://rzp.io/i/x") as link:
			self.assertEqual(portal.pay_online(self.invoice.name), "https://rzp.io/i/x")
		link.assert_called_once_with(self.invoice.name)
