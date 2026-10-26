# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Setting up a new customer site: `bench --site <site> rent-onboard ...` (run by signup.py,
or by hand for customers you sign up yourself)."""

import frappe
from frappe.installer import update_site_config

from rent_management import subscription

INVITE_LINK_HOURS = 48


def extend_invite_links():
	"""Set-password links from invites are often opened hours later; Frappe's default is 20 minutes."""
	current = frappe.db.get_single_value("System Settings", "reset_password_link_expiry_duration")
	if not current or int(current) == 1200:
		frappe.db.set_single_value(
			"System Settings", "reset_password_link_expiry_duration", INVITE_LINK_HOURS * 3600
		)


def onboard(
	email, full_name, business=None, phone=None, city=None, invoice_prefix=None, host_name=None
) -> dict:
	first_name, _sep, last_name = (full_name or "Manager").strip().partition(" ")
	email = email.strip().lower()

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"mobile_no": phone or None,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	user.add_roles("Rent Manager")

	subscription.update_subscription(billing_name=business or None, billing_email=email)
	settings = frappe.get_single("Rent Management Settings")
	settings.landlord_name = settings.landlord_name or full_name
	settings.landlord_phone = settings.landlord_phone or phone
	settings.flags.ignore_permissions = True
	settings.save()

	# the building created on install takes the business's name
	if (
		business
		and frappe.db.exists("Rent Property", "Main Building")
		and not frappe.db.exists("Rent Property", business)
	):
		if not frappe.db.count("Tenant Space"):
			frappe.rename_doc("Rent Property", "Main Building", business, force=True)
	if city and frappe.db.exists("Rent Property", business or "Main Building"):
		frappe.db.set_value("Rent Property", business or "Main Building", "city", city)

	if invoice_prefix:
		update_site_config("rent_invoice_prefix", invoice_prefix)
	if host_name:
		# links made outside a web request (emails, the set-password link below) use it
		update_site_config("host_name", host_name)
		frappe.local.conf.host_name = host_name
	extend_invite_links()
	return {"user": user.name, "set_password_link": user._reset_password(send_email=False)}
