# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Moving out (move_out.py): tenants are told their deposit comes back within 7 days."""
	if not frappe.db.get_single_value("Rent Management Settings", "deposit_refund_days"):
		frappe.db.set_single_value("Rent Management Settings", "deposit_refund_days", 7)
