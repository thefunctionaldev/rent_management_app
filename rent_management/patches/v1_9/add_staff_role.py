# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Staff logins (access.py): the role their DocType permissions are for, before those are synced."""
	if not frappe.db.exists("Role", "Rent Staff"):
		frappe.get_doc({"doctype": "Role", "role_name": "Rent Staff", "desk_access": 0}).insert(
			ignore_permissions=True
		)
