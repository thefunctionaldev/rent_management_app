# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import api, notices, portal, pwa
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


def run_now(method, **kwargs):
	frappe.get_attr(method)(
		**{k: v for k, v in kwargs.items() if k not in ("queue", "timeout", "enqueue_after_commit")}
	)


class TestNotices(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(notices.NOTICE)
		frappe.db.delete(notices.READ)
		self.a, self.b = make_property(), make_property()
		room = make_room(rent=7000, capacity=2, property=self.a)
		email = f"nisha.{frappe.generate_hash(length=5)}@tenant.example"
		self.nisha = frappe.get_doc({"doctype": "Tenant", "first_name": "Nisha", "email_id": email}).insert()
		make_allotment(room=room, tenant=self.nisha, allotment_date=add_days(nowdate(), -20))
		make_allotment(room=room, allotment_date=add_days(nowdate(), -20))
		self.other = make_allotment(
			room=make_room(rent=6000, property=self.b), allotment_date=add_days(nowdate(), -20)
		)
		api.invite_tenant(self.nisha.name)
		self.user = frappe.db.get_value("Tenant", self.nisha.name, "user")

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_tenant(self, method, *args):
		frappe.set_user(self.user)
		try:
			return method(*args)
		finally:
			frappe.set_user("Administrator")

	def publish(self, **values):
		data = {
			"title": "Water cut tomorrow",
			"message": "No water 10 am to 2 pm.\nPlease store some.",
			**values,
		}
		with patch.object(frappe, "enqueue", run_now):
			return api.save_notice(data, publish=1)

	def test_reaches_the_building(self):
		name = self.publish(property=self.a)
		doc = frappe.get_doc(notices.NOTICE, name)
		self.assertEqual((doc.status, doc.recipients, doc.published_by), ("Published", 2, "Administrator"))
		self.assertEqual(self.as_tenant(portal.get_boot)["notices_unread"], 1)
		self.assertEqual(self.as_tenant(portal.get_home)["notice"]["title"], "Water cut tomorrow")

		board = self.as_tenant(portal.get_notices)
		self.assertEqual([(n.title, n.unread) for n in board], [("Water cut tomorrow", True)])
		self.assertEqual(self.as_tenant(portal.get_boot)["notices_unread"], 0)  # seen now
		self.assertEqual(frappe.db.get_value(notices.NOTICE, name, "seen"), 1)
		self.assertEqual(api.get_notices(self.a)["notices"][0]["seen"], 1)

		# not shown in the other building
		self.assertEqual(notices.current(self.other), [])
		self.assertRaises(frappe.ValidationError, api.publish_notice, name)  # already published

	def test_all_buildings_expiry_and_taking_down(self):
		everyone = self.publish(pinned=1)
		self.assertEqual(
			frappe.db.get_value(notices.NOTICE, everyone, "recipients"), len(notices.tenants_for())
		)
		self.assertIn(str(self.nisha.name), notices.tenants_for())
		self.assertEqual([n.name for n in notices.current(self.other)], [everyone])

		old = self.publish(title="Diwali party", expires_on=nowdate())
		frappe.db.set_value(notices.NOTICE, old, "expires_on", add_days(nowdate(), -1))
		self.assertNotIn(old, [n.name for n in notices.current(self.other)])
		self.assertRaises(
			frappe.ValidationError,
			api.save_notice,
			{"title": "x", "message": "y", "expires_on": add_days(nowdate(), -1)},
		)

		api.take_down_notice(everyone)
		self.assertEqual(notices.current(self.other), [])
		api.delete_notice(everyone)
		self.assertFalse(frappe.db.exists(notices.NOTICE, everyone))

	def test_whatsapp_and_phones(self):
		frappe.set_user(self.user)
		pwa.subscribe("https://fcm.googleapis.com/fcm/send/nisha", "Tenant")
		frappe.set_user("Administrator")
		sent = []
		with (
			patch("rent_management.notifications.send", lambda *a, **kw: sent.append(a) or ["Sent"]),
			patch.object(pwa, "send_push") as push,
		):
			name = self.publish(property=self.a, send_whatsapp=1)
		push.assert_called_once_with(self.user)
		self.assertEqual(len(sent), 2)
		params = sent[0][3]
		self.assertNotIn("\n", params[3])  # WhatsApp template values are one line
		self.assertIn("No water 10 am to 2 pm. · Please store some.", params[3])
		self.assertEqual(frappe.db.get_value(notices.NOTICE, name, "messages_sent"), 2)

		# the woken phone asks what's new
		frappe.set_user(self.user)
		self.assertEqual(pwa.pending()[0]["url"], "/tenant/notices")
