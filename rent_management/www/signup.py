# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe

from rent_management.saas import is_control_site

no_cache = 1


def get_context(context):
	if not is_control_site():
		raise frappe.PageDoesNotExistError
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.no_cache = 1
	return context
