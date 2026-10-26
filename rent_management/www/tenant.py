# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from rent_management.portal import get_tenant

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.path)
		raise frappe.Redirect

	if not get_tenant():
		frappe.throw(
			_("Your login isn't linked to a tenant. Ask your landlord to invite you to the tenant app."),
			frappe.PermissionError,
		)

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.no_cache = 1
	return context
