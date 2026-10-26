# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Profit and loss per building and month.

Income is rent collected (Rent Payments by payment date, excluding payments made from
security deposits, which are not new money); invoiced rent is shown alongside. Expenses are
Property Expenses by date. Profit = collected - expenses.
"""

from collections import defaultdict

import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS


def month_key(date) -> str:
	return getdate(date).strftime("%Y-%m")


def get_profit_and_loss(months: int = 12, property=None, end=None) -> dict:
	end = get_last_day(getdate(end or nowdate()))
	start = get_first_day(add_months(end, -(months - 1)))
	keys = [month_key(add_months(start, i)) for i in range(months)]
	rows = {k: {"month": k, "invoiced": 0.0, "collected": 0.0, "expenses": 0.0} for k in keys}
	by_property = defaultdict(lambda: {"invoiced": 0.0, "collected": 0.0, "expenses": 0.0})
	categories = defaultdict(float)

	base = {"property": property} if property else {}
	for p in frappe.get_all(
		"Rent Payment",
		filters={
			**base,
			"docstatus": 1,
			"mode_of_payment": ("!=", "Security Deposit"),
			"payment_date": ("between", (start, end)),
		},
		fields=["payment_date", "amount", "property"],
	):
		rows[month_key(p.payment_date)]["collected"] += flt(p.amount)
		by_property[p.property]["collected"] += flt(p.amount)

	for inv in frappe.get_all(
		"Tenant Rent Invoice",
		filters={**base, "docstatus": 1, "billing_year": ("between", (start.year, end.year))},
		fields=["billing_month", "billing_year", "final_amount", "property"],
	):
		key = f"{inv.billing_year}-{MONTHS.index(inv.billing_month) + 1:02d}"
		if key in rows:
			rows[key]["invoiced"] += flt(inv.final_amount)
			by_property[inv.property]["invoiced"] += flt(inv.final_amount)

	for e in frappe.get_all(
		"Property Expense",
		filters={**base, "expense_date": ("between", (start, end))},
		fields=["expense_date", "amount", "category", "property"],
	):
		rows[month_key(e.expense_date)]["expenses"] += flt(e.amount)
		by_property[e.property]["expenses"] += flt(e.amount)
		categories[e.category] += flt(e.amount)

	def with_profit(row):
		row["profit"] = flt(row["collected"] - row["expenses"], 2)
		row["margin"] = round(row["profit"] / row["collected"] * 100) if row["collected"] else None
		return row

	totals = with_profit(
		{field: sum(r[field] for r in rows.values()) for field in ("invoiced", "collected", "expenses")}
	)
	return {
		"from_date": start,
		"to_date": end,
		"months": [with_profit(rows[k]) for k in keys],
		"totals": totals,
		"categories": sorted(
			({"category": c, "amount": a} for c, a in categories.items()), key=lambda r: -r["amount"]
		),
		"properties": sorted(
			(with_profit({"property": p, **v}) for p, v in by_property.items() if p),
			key=lambda r: -r["collected"],
		),
	}
