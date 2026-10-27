# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Self check-in for a new tenant (frontend/src/checkin): details, ID and the agreement."""

import frappe

no_cache = 1


def get_context(context):
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.no_cache = 1
	return context
