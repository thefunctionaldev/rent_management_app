# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Renewals (renewals.py): the current agreement of every stay so far started at move-in."""
	frappe.db.sql(
		"""update `tabTenant Space Allotment` set agreement_start_date = allotment_date
		where agreement_start_date is null"""
	)
