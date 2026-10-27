# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Invoices made before instalments: the next due date is the due date."""
	frappe.db.sql(
		"""update `tabTenant Rent Invoice` set next_due_date = due_date
		where next_due_date is null and due_date is not null"""
	)
