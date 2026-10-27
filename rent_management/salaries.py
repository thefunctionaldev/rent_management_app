# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Staff and salaries.

Each staff member works at a building and has a monthly salary. Every month the manager
prepares the salary slips (one per person), adjusts days off without pay, bonus and other
deductions, and pays them. Advances given during the month are recovered from the next
salaries (all at once, or a fixed amount a month).

Money paid out is a Salaries expense of the building, so profit and loss stays right: an
advance is an expense when it is given, and a salary when it is paid (net of what was
recovered), which adds up to the full salary.
"""

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, cint, date_diff, flt, get_last_day, getdate, nowdate

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

STAFF = "Staff Member"
ADVANCE = "Staff Advance"
SLIP = "Salary Slip"
CATEGORY = "Salaries"
MODES = ("Bank Transfer", "UPI", "Cash", "Cheque", "Other")


def month_range(month, year) -> tuple[date, date]:
	start = date(cint(year), MONTHS.index(month) + 1, 1)
	return start, get_last_day(start)


def last_month() -> tuple[str, int]:
	day = add_months(getdate(nowdate()), -1)
	return MONTHS[day.month - 1], day.year


def employed_days(staff, month, year) -> int:
	start, end = month_range(month, year)
	first = max(start, getdate(staff.joining_date))
	last = min(end, getdate(staff.leaving_date)) if staff.leaving_date else end
	return max(date_diff(last, first) + 1, 0)


def staff_for(month, year, property=None) -> list:
	"""Everyone who worked some of the month."""
	start, end = month_range(month, year)
	filters = {"joining_date": ("<=", end)}
	if property:
		filters["property"] = property
	return frappe.get_all(
		STAFF,
		filters=filters,
		or_filters=[["leaving_date", "is", "not set"], ["leaving_date", ">=", start]],
		pluck="name",
		order_by="staff_name asc",
	)


# ---------------------------------------------------------------- slips


def calculate(slip):
	"""Salary for the days paid, plus bonus, less deductions and advances recovered."""
	staff = frappe.get_cached_doc(STAFF, slip.staff)
	_start, end = month_range(slip.salary_month, slip.salary_year)
	if not slip.monthly_salary:
		slip.monthly_salary = staff.monthly_salary
	slip.days_in_month = end.day
	slip.days_employed = employed_days(staff, slip.salary_month, slip.salary_year)
	if not slip.days_employed:
		frappe.throw(
			_("{0} didn't work in {1} {2}.").format(staff.staff_name, slip.salary_month, slip.salary_year)
		)
	if flt(slip.unpaid_days) < 0 or flt(slip.unpaid_days) > slip.days_employed:
		frappe.throw(_("Days off without pay must be between 0 and {0}.").format(slip.days_employed))
	slip.days_paid = flt(slip.days_employed - flt(slip.unpaid_days), 2)
	full = slip.days_paid == slip.days_in_month
	slip.earned = flt(
		slip.monthly_salary if full else flt(slip.monthly_salary) / slip.days_in_month * slip.days_paid, 0
	)
	for field in ("bonus", "other_deduction"):
		if flt(slip.get(field)) < 0:
			frappe.throw(_("{0} can't be negative.").format(slip.meta.get_label(field)))
	payable = flt(slip.earned) + flt(slip.bonus) - flt(slip.other_deduction)
	if payable < 0:
		frappe.throw(_("The deductions are more than the salary."))

	slip.set("recoveries", [])
	if cint(slip.recover_advances):
		for advance in frappe.get_all(
			ADVANCE,
			filters={"staff": slip.staff, "status": "Open", "advance_date": ("<=", end)},
			fields=["name", "outstanding", "recover_per_month"],
			order_by="advance_date asc, creation asc",
		):
			amount = min(
				flt(advance.outstanding), flt(advance.recover_per_month) or flt(advance.outstanding), payable
			)
			if amount > 0:
				slip.append("recoveries", {"advance": advance.name, "amount": amount})
				payable -= amount
	slip.advance_recovery = sum(flt(r.amount) for r in slip.recoveries)
	slip.net_pay = flt(payable, 2)


def prepare(month, year, property=None) -> int:
	"""Draft slips for everyone who worked in the month and has none yet."""
	made = 0
	for name in staff_for(month, year, property):
		if frappe.db.exists(SLIP, {"staff": name, "salary_month": month, "salary_year": cint(year)}):
			continue
		frappe.get_doc(
			{"doctype": SLIP, "staff": name, "salary_month": month, "salary_year": cint(year)}
		).insert()
		made += 1
	return made


def get_salaries(month, year, property=None) -> dict:
	month = month or last_month()[0]
	year = cint(year) or last_month()[1]
	filters = {"salary_month": month, "salary_year": year}
	if property:
		filters["property"] = property
	slips = frappe.get_all(
		SLIP,
		filters=filters,
		fields=["name", "staff", "staff_name", "role", "property", "status", "monthly_salary", "days_in_month",
			"days_employed", "unpaid_days", "days_paid", "earned", "bonus", "other_deduction", "deduction_note",
			"recover_advances", "advance_recovery", "net_pay", "paid_on", "mode_of_payment", "reference_no"],
		order_by="staff_name asc",
	)  # fmt: skip
	staff = {
		s.name: s
		for s in frappe.get_all(
			STAFF,
			filters={"name": ("in", [s.staff for s in slips] or [""])},
			fields=["name", "mobile_no", "display_picture", "payment_mode", "upi_id", "bank_account_no",
				"ifsc_code", "pay_day"],
		)
	}  # fmt: skip
	for slip in slips:
		slip.staff_details = staff.get(slip.staff)
	missing = len(staff_for(month, year, property)) - len(slips)
	return {
		"month": month,
		"year": year,
		"slips": slips,
		"missing": max(missing, 0),
		"total": sum(flt(s.net_pay) for s in slips),
		"paid": sum(flt(s.net_pay) for s in slips if s.status == "Paid"),
	}


def save_slip(name, data):
	data = frappe.parse_json(data)
	slip = frappe.get_doc(SLIP, name)
	slip.update(
		{
			field: data.get(field)
			for field in (
				"unpaid_days",
				"bonus",
				"other_deduction",
				"deduction_note",
				"recover_advances",
				"note",
			)
			if field in data
		}
	)
	slip.save()
	return slip.name


def pay(name, paid_on=None, mode_of_payment=None, reference_no=None):
	slip = frappe.get_doc(SLIP, name)
	if slip.status == "Paid":
		frappe.throw(_("This salary is already paid."))
	calculate(slip)  # advances may have changed since it was prepared
	paid_on = getdate(paid_on or nowdate())
	staff = frappe.get_cached_doc(STAFF, slip.staff)
	expense = None
	if flt(slip.net_pay) > 0:
		expense = frappe.get_doc(
			{
				"doctype": "Property Expense",
				"property": slip.property,
				"expense_date": paid_on,
				"category": CATEGORY,
				"amount": slip.net_pay,
				"paid_to": slip.staff_name,
				"mode_of_payment": expense_mode(mode_of_payment or staff.payment_mode),
				"reference_no": reference_no,
				"description": _("Salary for {0} {1}").format(slip.salary_month, slip.salary_year),
			}
		).insert()
	slip.update(
		{
			"status": "Paid",
			"paid_on": paid_on,
			"mode_of_payment": mode_of_payment or staff.payment_mode,
			"reference_no": reference_no,
			"expense": expense.name if expense else None,
		}
	)
	slip.flags.paying = True
	slip.save()
	for row in slip.recoveries:
		recover(row.advance, row.amount)


def undo_payment(name):
	slip = frappe.get_doc(SLIP, name)
	if slip.status != "Paid":
		return
	expense = slip.expense
	for row in slip.recoveries:
		recover(row.advance, -flt(row.amount))
	slip.update({"status": "Draft", "paid_on": None, "reference_no": None, "expense": None})
	slip.flags.paying = True
	slip.save()
	if expense:
		frappe.delete_doc("Property Expense", expense)


def recover(advance, amount):
	doc = frappe.get_doc(ADVANCE, advance)
	doc.recovered = flt(doc.recovered) + flt(amount)
	doc.save()


def expense_mode(mode):
	"""Property Expense knows Card but not every mode the same way."""
	return mode if mode in ("Cash", "UPI", "Bank Transfer", "Cheque") else "Other"


# ---------------------------------------------------------------- advances


def give_advance(staff, amount, advance_date=None, recover_per_month=None, mode_of_payment="Cash", note=None):
	doc = frappe.get_doc(
		{
			"doctype": ADVANCE,
			"staff": staff,
			"amount": flt(amount),
			"advance_date": advance_date or nowdate(),
			"recover_per_month": flt(recover_per_month) or None,
			"mode_of_payment": mode_of_payment,
			"note": note,
		}
	).insert()
	return doc.name


def delete_advance(name):
	"""Only an advance nothing was recovered from yet; draft slips are worked out again."""
	slips = frappe.get_all("Salary Slip Advance", filters={"advance": name, "parenttype": SLIP}, pluck="parent")
	if any(frappe.db.get_value(SLIP, slip, "status") == "Paid" for slip in slips):
		frappe.throw(_("Part of this advance was recovered from a salary. Undo that salary payment first."))
	frappe.db.delete("Salary Slip Advance", {"advance": name, "parenttype": SLIP})
	frappe.delete_doc(ADVANCE, name)
	for slip in set(slips):
		frappe.get_doc(SLIP, slip).save()


def advance_expense(advance):
	"""An advance is money paid out the day it is given."""
	expense = frappe.get_doc(
		{
			"doctype": "Property Expense",
			"property": advance.property,
			"expense_date": advance.advance_date,
			"category": CATEGORY,
			"amount": advance.amount,
			"paid_to": advance.staff_name,
			"mode_of_payment": expense_mode(advance.mode_of_payment),
			"description": _("Salary advance") + (f": {advance.note}" if advance.note else ""),
		}
	).insert()
	advance.db_set("expense", expense.name)


# ---------------------------------------------------------------- staff list and reminders


def get_staff(property=None) -> dict:
	filters = {"property": property} if property else {}
	staff = frappe.get_all(
		STAFF,
		filters=filters,
		fields=["name", "staff_name", "role", "property", "mobile_no", "display_picture", "monthly_salary",
			"pay_day", "joining_date", "leaving_date", "is_active", "payment_mode", "upi_id", "bank_account_no",
			"ifsc_code", "address", "emergency_contact", "notes"],
		order_by="is_active desc, staff_name asc",
	)  # fmt: skip
	advances = frappe.get_all(
		ADVANCE,
		filters={**filters, "advance_date": (">=", add_months(nowdate(), -6))},
		fields=["name", "staff", "staff_name", "property", "advance_date", "amount", "recover_per_month",
			"recovered", "outstanding", "status", "mode_of_payment", "note"],
		order_by="advance_date desc",
	)  # fmt: skip
	owed = {}
	for a in advances:
		if a.status == "Open":
			owed[a.staff] = owed.get(a.staff, 0) + flt(a.outstanding)
	for s in staff:
		s.advance_due = owed.get(s.name, 0)
	active = [s for s in staff if s.is_active]
	return {
		"staff": staff,
		"advances": advances,
		"monthly_total": sum(flt(s.monthly_salary) for s in active),
		"advance_due": sum(owed.values()),
	}


def remind_due():
	"""Daily: on a pay day, tell managers whose salary for last month isn't paid yet."""
	from rent_management.portal import notify_managers

	month, year = last_month()
	today = getdate(nowdate())
	due = [
		s
		for s in frappe.get_all(
			STAFF,
			filters={"is_active": 1},
			fields=["name", "staff_name", "pay_day", "joining_date", "leaving_date"],
		)
		if min(max(cint(s.pay_day), 1), 28) == today.day
		and employed_days(s, month, year)
		and not frappe.db.exists(
			SLIP, {"staff": s.name, "salary_month": month, "salary_year": year, "status": "Paid"}
		)
	]
	if due:
		notify_managers(
			_("Salaries due for {0}").format(month),
			_("Today is pay day for {0}. Prepare and pay their {1} salary on the Staff page.").format(
				", ".join(s.staff_name for s in due), month
			),
		)
