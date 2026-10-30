# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.path)
		raise frappe.Redirect

	if not set(frappe.get_roles()) & {"System Manager", "Rent Manager", "Rent Staff"}:
		frappe.throw(_("You need the Rent Manager role to open this page."), frappe.PermissionError)

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.no_cache = 1
	return context
