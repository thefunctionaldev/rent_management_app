# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""The cash book (cash.py): cash recorded before it is held by whoever recorded it."""
	frappe.db.sql(
		"""update `tabRent Payment` p set collected_by =
			-- a tenant reported it: the manager who confirmed it has the cash
			if(p.owner in (select user from `tabTenant` where ifnull(user, '') != ''), p.modified_by, p.owner)
		where p.mode_of_payment = 'Cash' and p.docstatus = 1 and ifnull(p.collected_by, '') = ''"""
	)
	frappe.db.sql(
		"""update `tabProperty Expense` set paid_by = owner
		where mode_of_payment = 'Cash' and ifnull(paid_by, '') = ''"""
	)
