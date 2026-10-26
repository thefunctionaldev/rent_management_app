# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from rent_management import api, notifications, subscription
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


def whatsapp_ok(*args, **kwargs):
	response = MagicMock(ok=True, content=b"{}")
	response.json.return_value = {"messages": [{"id": "wamid.1"}]}
	return response


class TestNotifications(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete(notifications.LOG)
		settings = frappe.get_single("Rent Management Settings")
		settings.update(
			{
				"send_reminders": 1,
				"remind_days_before": 3,
				"remind_on_due_date": 1,
				"overdue_reminder_interval": 3,
				"overdue_reminder_limit": 2,
				"send_receipts": 1,
				"notify_by_whatsapp": 1,
				"notify_by_email": 1,
				"whatsapp_phone_number_id": "PNID",
				"whatsapp_token": "own-token",
				"razorpay_enabled": 0,
				"upi_id": "landlord@upi",
			}
		)
		settings.save()
		self.whatsapp = self.enterContext(
			patch.object(notifications.requests, "post", side_effect=whatsapp_ok)
		)
		self.email = self.enterContext(patch.object(notifications.frappe, "sendmail"))
		self.enterContext(patch.object(notifications, "email_configured", return_value=True))

		self.tenant = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": "Neha",
				"last_name": "Rao",
				"mobile_no": "98765 43210",
				"email_id": "neha@example.com",
			}
		).insert()
		allotment = make_allotment(room=make_room(rent=4000), tenant=self.tenant)
		self.invoice = make_invoice(
			allotment, posting_date=nowdate(), due_date=add_days(nowdate(), 3), submit=True
		)

	def logs(self, **filters):
		return frappe.get_all(
			notifications.LOG, filters=filters, fields=["message_type", "channel", "status", "recipient"]
		)

	def test_email_skipped_without_email_account(self):
		with patch.object(notifications, "email_configured", return_value=False):
			api.send_rent_reminder(self.invoice.name)
		self.assertEqual([log.channel for log in self.logs(rent_invoice=self.invoice.name)], ["WhatsApp"])

	def test_whatsapp_number(self):
		self.assertEqual(notifications.whatsapp_number("98765 43210"), "919876543210")
		self.assertEqual(notifications.whatsapp_number("09876543210"), "919876543210")
		self.assertEqual(notifications.whatsapp_number("+44 7700 900123"), "447700900123")
		self.assertIsNone(notifications.whatsapp_number("12345"))

	def test_reminder_schedule(self):
		settings = frappe.get_single("Rent Management Settings")
		due = getdate(self.invoice.due_date)
		kind = lambda days: notifications.get_reminder_type(self.invoice, settings, add_days(due, days))  # noqa: E731
		self.assertEqual(kind(-3), "Reminder")
		self.assertIsNone(kind(-2))
		self.assertEqual(kind(0), "Due Today")
		self.assertIsNone(kind(1))
		self.assertEqual(kind(3), "Overdue")
		self.assertEqual(kind(6), "Overdue")

	def test_daily_reminders_on_both_channels(self):
		notifications.send_due_reminders()
		logs = self.logs(rent_invoice=self.invoice.name)
		self.assertEqual(
			sorted((log.channel, log.status, log.recipient) for log in logs),
			[("Email", "Sent", "neha@example.com"), ("WhatsApp", "Sent", "919876543210")],
		)
		body = next(
			c.kwargs["json"] for c in self.whatsapp.call_args_list if c.kwargs["json"]["to"] == "919876543210"
		)
		self.assertEqual(body["template"]["name"], "rent_reminder")
		params = [p["text"] for p in body["template"]["components"][0]["parameters"]]
		self.assertEqual(params[0], "Neha")
		self.assertIn("landlord@upi", params[5])
		self.assertEqual(self.whatsapp.call_args.kwargs["headers"]["Authorization"], "Bearer own-token")

		self.assertIn(["neha@example.com"], [c.kwargs["recipients"] for c in self.email.call_args_list])

		# running again the same day sends nothing new
		notifications.send_due_reminders()
		self.assertEqual(len(self.logs(rent_invoice=self.invoice.name)), 2)

	def test_overdue_limit(self):
		frappe.db.set_value("Tenant Rent Invoice", self.invoice.name, "due_date", add_days(nowdate(), -3))
		self.invoice.reload()
		settings = frappe.get_single("Rent Management Settings")
		self.assertEqual(
			notifications.get_reminder_type(self.invoice, settings, getdate(nowdate())), "Overdue"
		)
		notifications.send_reminder(self.invoice, "Overdue")
		notifications.send_reminder(self.invoice, "Overdue")
		# two overdue reminders sent per channel: the limit of 2 is reached
		self.assertIsNone(notifications.get_reminder_type(self.invoice, settings, getdate(nowdate())))

	def test_failed_whatsapp_is_logged(self):
		error = MagicMock(ok=False, content=b"{}", reason="Bad Request")
		error.json.return_value = {"error": {"message": "Template not approved"}}
		self.whatsapp.side_effect = lambda *a, **k: error
		statuses = api.send_rent_reminder(self.invoice.name)
		self.assertEqual(sorted(statuses), ["Failed", "Sent"])
		failed = frappe.get_all(notifications.LOG, filters={"status": "Failed"}, fields=["error"])
		self.assertIn("Template not approved", failed[0].error)

	def test_receipt_on_payment(self):
		payment = api.record_payment(self.invoice.name, 1500, "Cash")
		logs = self.logs(rent_payment=payment)
		self.assertEqual({log.message_type for log in logs}, {"Receipt"})
		self.assertEqual(len(logs), 2)
		params = [
			p["text"]
			for p in self.whatsapp.call_args.kwargs["json"]["template"]["components"][0]["parameters"]
		]
		self.assertEqual(self.whatsapp.call_args.kwargs["json"]["template"]["name"], "rent_receipt")
		self.assertIn("1,500", params[1])
		self.assertIn("2,500", params[4])  # balance

	def test_whatsapp_from_your_account_needs_the_plan(self):
		frappe.get_single("Rent Management Settings").db_set("whatsapp_phone_number_id", None)
		with patch.dict(
			frappe.conf, {"whatsapp_phone_number_id": "VENDOR", "whatsapp_token": "vendor-token"}
		):
			frappe.flags.enforce_rent_subscription = True
			try:
				with patch.object(subscription, "get_current_plan", return_value={"whatsapp": 0}):
					self.assertIsNone(notifications.get_whatsapp_account())
				with patch.object(subscription, "get_current_plan", return_value={"whatsapp": 1}):
					self.assertEqual(notifications.get_whatsapp_account(), ("VENDOR", "vendor-token"))
			finally:
				frappe.flags.enforce_rent_subscription = False

	def test_settings_secrets_are_write_only(self):
		data = api.get_settings()
		self.assertNotIn("whatsapp_token", data["settings"])
		self.assertTrue(data["settings"]["whatsapp_token_set"])
		self.assertEqual(data["whatsapp"]["source"], "own")

		api.save_settings({"upi_id": "new@upi", "whatsapp_token": ""})  # blank keeps the saved token
		settings = frappe.get_single("Rent Management Settings")
		self.assertEqual(settings.upi_id, "new@upi")
		self.assertEqual(settings.get_password("whatsapp_token"), "own-token")
		api.save_settings({"clear_whatsapp_token": 1})
		self.assertFalse(api.get_settings()["settings"]["whatsapp_token_set"])
