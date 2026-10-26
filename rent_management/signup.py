# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Self-serve signup on the control site (/signup).

1. The visitor fills in the form: a SaaS Signup is saved and a verification link is emailed.
2. The link verifies the email address and queues the provisioning job.
3. The job runs `bench new-site <sub>.<domain> --install-app rent_management` and
   `bench --site <site> rent-onboard ...` (creates their Rent Manager login, billing details,
   building, invoice prefix), runs your optional post-provision command (nginx, SSL...), and
   shows / emails the link to set their password. The free trial starts on install.

Control site config:

    "rent_signup_domain": "rentapp.in",          # sites become <subdomain>.rentapp.in
    "rent_bench_command": "bench",               # if bench isn't on the worker's PATH
    "rent_signup_post_provision": "sudo -n /usr/local/bin/rent-new-site {site}",   # optional
    "rent_signup_scheme": "https",               # http only for local testing

and `root_password` (MariaDB root) in common_site_config.json so new-site doesn't prompt.
"""

import json
import os
import re
import shlex
import subprocess

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import (
	cint,
	get_url,
	now_datetime,
	random_string,
	time_diff_in_hours,
	validate_email_address,
)

from rent_management.notifications import email_configured
from rent_management.saas import CUSTOMER, only_control_site

SIGNUP = "SaaS Signup"
SUBDOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,28}[a-z0-9])$")
RESERVED = {
	"www", "admin", "app", "api", "mail", "smtp", "control", "signup", "login", "help", "support",
	"billing", "status", "test", "demo", "dev", "staging", "static", "assets", "files", "rent", "tenant",
}  # fmt: skip


def get_domain() -> str:
	domain = frappe.conf.get("rent_signup_domain")
	if not domain:
		frappe.throw(_("Signups are not open yet."))
	return domain.strip(".").lower()


def bench_path() -> str:
	return frappe.utils.get_bench_path()


def site_exists(site: str) -> bool:
	return os.path.exists(os.path.join(bench_path(), "sites", site))


def check_subdomain(subdomain: str) -> str:
	"""Normalise and validate a subdomain, returning the full site name."""
	subdomain = (subdomain or "").strip().lower()
	if not SUBDOMAIN.match(subdomain) or "--" in subdomain:
		frappe.throw(_("Use 3 to 30 letters, numbers or hyphens for your address."))
	if subdomain in RESERVED:
		frappe.throw(_("{0} is reserved. Please choose another address.").format(subdomain))
	site = f"{subdomain}.{get_domain()}"
	taken = frappe.db.exists(SIGNUP, {"subdomain": subdomain, "status": ("!=", "Failed")})
	if taken or site_exists(site) or frappe.db.exists(CUSTOMER, site):
		frappe.throw(_("{0} is taken. Please choose another address.").format(site))
	return site


def make_invoice_prefix(subdomain: str) -> str:
	base = re.sub(r"[^A-Z0-9]", "", subdomain.upper())[:6] or "RENT"
	prefix, n = base, 1
	while frappe.db.exists(SIGNUP, {"invoice_prefix": prefix}):
		n += 1
		prefix = f"{base[: 6 - len(str(n))]}{n}"
	return prefix


# ---------------------------------------------------------------- public endpoints


@frappe.whitelist(allow_guest=True)
def get_plans():
	"""Plans and prices for the signup page."""
	only_control_site()
	from rent_management.subscription import get_currency, trial_days
	from rent_management.subscription import get_plans as plans

	return {
		"trial_days": trial_days(),
		"currency": get_currency(),
		"domain": get_domain(),
		"brand": frappe.conf.get("rent_subscription_brand") or "Rent Management",
		"plans": [
			{
				"key": key,
				"title": plan.get("title", key),
				"description": plan.get("description"),
				"monthly": plan.get("monthly"),
				"yearly": plan.get("yearly"),
				"features": plan.get("features") or [],
			}
			for key, plan in plans().items()
		],
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=60 * 60)
def is_available(subdomain):
	only_control_site()
	try:
		return {"available": True, "site": check_subdomain(subdomain)}
	except frappe.ValidationError as e:
		frappe.clear_messages()
		return {"available": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def signup(full_name, business_name, email, subdomain, phone=None, city=None, beds=None, website=None):
	"""Start a signup. `website` is a honeypot: people leave it empty, bots fill it in."""
	only_control_site()
	if website:
		return {"status": "Pending Verification"}  # pretend all is well

	email = (email or "").strip().lower()
	if not validate_email_address(email):
		frappe.throw(_("Please enter a valid email address."))
	if not (full_name or "").strip() or not (business_name or "").strip():
		frappe.throw(_("Please enter your name and your business name."))
	site = check_subdomain(subdomain)
	skip_verification = bool(frappe.conf.get("rent_signup_skip_verification"))
	if not skip_verification and not email_configured():
		frappe.log_error(title="Signup refused: no outgoing email account on the control site")
		frappe.throw(_("Signups are temporarily unavailable. Please try again later."))

	doc = frappe.get_doc(
		{
			"doctype": SIGNUP,
			"full_name": full_name.strip()[:140],
			"business_name": business_name.strip()[:140],
			"email": email,
			"phone": (phone or "").strip()[:20] or None,
			"city": (city or "").strip()[:80] or None,
			"beds": cint(beds) or None,
			"subdomain": site.split(".")[0],
			"site": site,
			"invoice_prefix": make_invoice_prefix(site.split(".")[0]),
			"token": random_string(32),
			"ip_address": frappe.local.request_ip,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()

	if skip_verification:
		# for testing the flow on a server without email
		verify(doc.token)
		return {"status": "Verified", "token": doc.token}

	link = get_url(f"/signup?token={doc.token}")
	frappe.sendmail(
		recipients=[email],
		subject=_("Confirm your email to create {0}").format(site),
		message=_(
			"<p>Hello {0},</p><p>Click the link below to confirm your email address. We'll then set up "
			"<b>{1}</b> for {2}, with a free trial.</p><p><a href='{3}'>{3}</a></p>"
			"<p>If you didn't sign up, ignore this email.</p>"
		).format(doc.full_name, site, doc.business_name, link),
		now=True,
	)
	return {"status": "Pending Verification"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def verify(token):
	only_control_site()
	name = frappe.db.get_value(SIGNUP, {"token": token})
	if not name:
		frappe.throw(_("This link is not valid."))
	doc = frappe.get_doc(SIGNUP, name)
	if doc.status == "Pending Verification":
		doc.db_set({"status": "Verified", "verified_on": now_datetime()})
		frappe.enqueue(
			"rent_management.signup.provision",
			queue="long",
			timeout=1800,
			signup=doc.name,
			enqueue_after_commit=True,
			now=bool(frappe.flags.in_test),
		)
	return get_status(token)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=600, seconds=60 * 60)
def get_status(token):
	only_control_site()
	doc = frappe.db.get_value(
		SIGNUP,
		{"token": token},
		["status", "site", "business_name", "set_password_link", "provisioned_on"],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("This link is not valid."))
	result = {"status": doc.status, "site": doc.site, "business_name": doc.business_name}
	if doc.status == "Active":
		result["url"] = f"{frappe.conf.get('rent_signup_scheme') or 'https'}://{doc.site}/rent"
		# only shown for a day, after that "Forgot password" on their login page
		if doc.provisioned_on and time_diff_in_hours(now_datetime(), doc.provisioned_on) < 24:
			result["set_password_link"] = doc.set_password_link
	return result


# ---------------------------------------------------------------- provisioning job


def run(args, timeout=1200) -> str:
	result = subprocess.run(args, cwd=bench_path(), capture_output=True, text=True, timeout=timeout)
	if result.returncode:
		output = (result.stdout + "\n" + result.stderr).strip()
		raise RuntimeError(f"{' '.join(shlex.quote(a) for a in args[:3])} failed:\n{output[-2000:]}")
	return result.stdout


def provision(signup: str):
	doc = frappe.get_doc(SIGNUP, signup)
	if doc.status not in ("Verified", "Failed"):
		return
	doc.db_set({"status": "Provisioning", "error": None})
	commit()  # the signup page shows progress while the site is created

	bench = frappe.conf.get("rent_bench_command") or "bench"
	try:
		if not site_exists(doc.site):
			run(
				[
					bench,
					"new-site",
					doc.site,
					"--install-app",
					"rent_management",
					"--admin-password",
					random_string(24),
				]
			)
		output = run(
			[
				bench, "--site", doc.site, "rent-onboard",
				"--email", doc.email,
				"--full-name", doc.full_name,
				"--business", doc.business_name,
				"--phone", doc.phone or "",
				"--city", doc.city or "",
				"--invoice-prefix", doc.invoice_prefix or "",
				"--host-name", f"{frappe.conf.get('rent_signup_scheme') or 'https'}://{doc.site}",
			],
			timeout=300,
		)  # fmt: skip
		result = json.loads(output.strip().splitlines()[-1])

		post = frappe.conf.get("rent_signup_post_provision")
		if post:
			run(shlex.split(post.format(site=doc.site)), timeout=300)
	except Exception as e:
		doc.db_set({"status": "Failed", "error": str(e)[-5000:]})
		frappe.log_error(title=f"Provisioning {doc.site} failed")
		commit()
		return

	doc.db_set(
		{
			"status": "Active",
			"provisioned_on": now_datetime(),
			"set_password_link": result.get("set_password_link"),
		}
	)
	if not frappe.db.exists(CUSTOMER, doc.site):
		frappe.get_doc(
			{
				"doctype": CUSTOMER,
				"site": doc.site,
				"billing_name": doc.business_name,
				"contact_email": doc.email,
				"contact_phone": doc.phone,
				"signup": doc.name,
				"status": "Trial",
			}
		).insert(ignore_permissions=True)
	commit()

	# the signup page already shows the link; the email is a copy, so it never fails the signup
	if email_configured():
		try:
			frappe.sendmail(
				recipients=[doc.email],
				subject=_("{0} is ready").format(doc.site),
				message=_(
					"<p>Hello {0},</p><p>Your rent management account for {1} is ready at "
					"<a href='https://{2}/rent'>https://{2}/rent</a>.</p>"
					"<p>Set your password here (or use Forgot Password on the login page): "
					"<a href='{3}'>{3}</a></p>"
					"<p>Your free trial has started. Reply to this email if you need any help.</p>"
				).format(doc.full_name, doc.business_name, doc.site, result.get("set_password_link")),
			)
		except Exception:
			frappe.log_error(title=f"Could not email {doc.email} that {doc.site} is ready")


def commit():
	# a background job's progress must be visible to the signup page; tests roll back instead
	if not frappe.flags.in_test:
		frappe.db.commit()


@frappe.whitelist()
def retry(signup):
	"""Desk button for System Managers: run a failed provisioning again."""
	only_control_site()
	frappe.only_for("System Manager")
	frappe.db.set_value(SIGNUP, signup, "status", "Verified")
	frappe.enqueue("rent_management.signup.provision", queue="long", timeout=1800, signup=signup)
