# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import onboarding, saas, signup, subscription

CONF = {
	"rent_control_site": 1,
	"rent_signup_domain": "rentapp.example",
	"rent_bench_command": "bench",
	"rent_signup_skip_verification": 0,
	"rent_signup_post_provision": None,
}


def no_bench(*args, **kwargs):
	raise AssertionError(f"unexpected command in a test: {args}")


def bench_ok(args, **kwargs):
	"""Stand-in for subprocess.run: new-site and rent-onboard succeed."""
	out = (
		json.dumps({"user": "x", "set_password_link": "https://x/update-password?key=abc"})
		if "rent-onboard" in args
		else ""
	)
	return MagicMock(returncode=0, stdout=out, stderr="")


class TestSignup(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.enterContext(patch.dict(frappe.conf, CONF))
		self.mail = self.enterContext(patch.object(signup.frappe, "sendmail"))
		self.enterContext(patch.object(signup, "email_configured", return_value=True))
		self.enterContext(patch.object(signup, "site_exists", return_value=False))
		# never create real sites from a test; tests that expect commands patch this again
		self.enterContext(patch.object(signup.subprocess, "run", side_effect=no_bench))
		frappe.cache.delete_keys("rate-limit-counter")  # the endpoints are rate limited per IP

	def start(self, subdomain=None, **kwargs):
		subdomain = subdomain or "pg-" + frappe.generate_hash(length=6)
		values = {
			"full_name": "Ravi Sharma",
			"business_name": "Sharma PG",
			"email": f"{subdomain}@example.com",
			"subdomain": subdomain,
			"phone": "+91 98765 43210",
			**kwargs,
		}
		frappe.set_user("Guest")
		try:
			return signup.signup(**values), subdomain
		finally:
			frappe.set_user("Administrator")

	def test_subdomain_rules(self):
		self.assertTrue(signup.is_available("sunrise-pg")["available"])
		for bad in ("ab", "-abc", "abc-", "a--b", "has space", "UPPER_case", "admin", "x" * 31):
			self.assertFalse(signup.is_available(bad)["available"], bad)
		_result, taken = self.start()
		self.assertFalse(signup.is_available(taken)["available"])
		with patch.object(signup, "site_exists", return_value=True):
			self.assertFalse(signup.is_available("existing-site")["available"])

	def test_signup_verify_and_provision(self):
		result, subdomain = self.start()
		self.assertEqual(result, {"status": "Pending Verification"})
		doc = frappe.get_doc(signup.SIGNUP, {"subdomain": subdomain})
		self.assertEqual(doc.site, f"{subdomain}.rentapp.example")
		self.assertIn(doc.token, self.mail.call_args.kwargs["message"])

		with patch.object(signup.subprocess, "run", side_effect=bench_ok) as run:
			status = signup.verify(doc.token)
		commands = [call.args[0] for call in run.call_args_list]
		self.assertEqual(commands[0][:4], ["bench", "new-site", doc.site, "--install-app"])
		self.assertIn("rent-onboard", commands[1])
		self.assertEqual(commands[1][commands[1].index("--invoice-prefix") + 1], doc.invoice_prefix)
		self.assertEqual(commands[1][commands[1].index("--host-name") + 1], f"https://{doc.site}")

		self.assertEqual(status["status"], "Active")
		self.assertEqual(status["set_password_link"], "https://x/update-password?key=abc")
		customer = frappe.get_doc(saas.CUSTOMER, doc.site)
		self.assertEqual((customer.status, customer.billing_name), ("Trial", "Sharma PG"))
		# verifying twice doesn't provision again
		with patch.object(signup.subprocess, "run", side_effect=bench_ok) as run:
			signup.verify(doc.token)
		run.assert_not_called()

	def test_failed_provisioning(self):
		_result, subdomain = self.start()
		doc = frappe.get_doc(signup.SIGNUP, {"subdomain": subdomain})
		failure = MagicMock(returncode=1, stdout="", stderr="Access denied for user root")
		with patch.object(signup.subprocess, "run", return_value=failure):
			status = signup.verify(doc.token)
		self.assertEqual(status["status"], "Failed")
		self.assertIn("Access denied", frappe.db.get_value(signup.SIGNUP, doc.name, "error"))
		self.assertNotIn("set_password_link", status)

		# a failed signup can be provisioned again (the desk's Provision Again button)
		with patch.object(signup.subprocess, "run", side_effect=bench_ok):
			signup.provision(doc.name)
		self.assertEqual(frappe.db.get_value(signup.SIGNUP, doc.name, "status"), "Active")

	def test_honeypot_and_validation(self):
		result, subdomain = self.start(website="http://spam.example")
		self.assertEqual(result["status"], "Pending Verification")
		self.assertFalse(frappe.db.exists(signup.SIGNUP, {"subdomain": subdomain}))
		self.assertRaises(frappe.ValidationError, self.start, email="not-an-email")
		self.assertRaises(frappe.ValidationError, self.start, subdomain="www")

	def test_invoice_prefixes_are_unique(self):
		_r, first = self.start("sharma-pg-" + frappe.generate_hash(length=3))
		_r, second = self.start("sharma-hostel-" + frappe.generate_hash(length=3))
		prefixes = {
			frappe.db.get_value(signup.SIGNUP, {"subdomain": s}, "invoice_prefix") for s in (first, second)
		}
		self.assertEqual(len(prefixes), 2)
		self.assertTrue(all(len(p) <= 6 for p in prefixes))

	def test_signup_needs_email_for_verification(self):
		with patch.object(signup, "email_configured", return_value=False):
			self.assertRaises(frappe.ValidationError, self.start)
			with patch.dict(frappe.conf, {"rent_signup_skip_verification": 1}):
				with patch.object(signup.subprocess, "run", side_effect=bench_ok):
					result, _subdomain = self.start()
		self.assertEqual(result["status"], "Verified")

	def test_only_on_control_site(self):
		with patch.dict(frappe.conf, {"rent_control_site": 0}):
			self.assertRaises(frappe.PermissionError, signup.is_available, "abc")

	def test_onboard_sets_up_the_customer_site(self):
		with patch.object(onboarding, "update_site_config") as update_config:
			result = onboarding.onboard(
				"owner.onboard@example.com",
				"Meena Iyer",
				"Iyer Hostel",
				"+91 90000 11111",
				"Chennai",
				"IYER",
				"https://iyer.example",
			)
		self.assertIn("Rent Manager", frappe.get_roles("owner.onboard@example.com"))
		self.assertIn("update-password?key=", result["set_password_link"])
		self.assertEqual(frappe.db.get_single_value(subscription.SUBSCRIPTION, "billing_name"), "Iyer Hostel")
		update_config.assert_any_call("rent_invoice_prefix", "IYER")
		update_config.assert_any_call("host_name", "https://iyer.example")
		self.assertTrue(result["set_password_link"].startswith("https://iyer.example/update-password"))
		self.assertEqual(
			int(frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration")),
			48 * 3600,
		)
