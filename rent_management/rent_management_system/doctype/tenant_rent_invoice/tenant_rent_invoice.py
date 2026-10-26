# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, date_diff, flt, get_last_day, getdate, nowdate

from rent_management.rent_management_system.doctype.meter_reading.meter_reading import (
	add_meter_charges,
	link_meter_charges,
	unlink_meter_charges,
)

MONTHS = list(calendar.month_name)[1:]


class TenantRentInvoice(Document):
	def validate(self):
		if not (self.tenant_space_allotment and self.billing_month and self.billing_year):
			return  # let the standard mandatory check report what is missing

		self.set_allotment_details()
		self.validate_duplicate()
		self.set_billing_period()
		self.calculate_totals()
		self.set_due_date()
		self.set_status()

	def before_insert(self):
		# electricity from meter readings since the last invoice
		if self.tenant_space_allotment and not self.flags.skip_meter_charges:
			add_meter_charges(self)

	def on_update(self):
		link_meter_charges(self)

	def on_submit(self):
		self.set_status(update=True)

	def on_cancel(self):
		self.set_status(update=True)
		unlink_meter_charges(self)

	def on_trash(self):
		unlink_meter_charges(self)

	def set_allotment_details(self):
		allotment = frappe.db.get_value(
			"Tenant Space Allotment",
			self.tenant_space_allotment,
			["docstatus", "tenant", "room", "rent_amount"],
			as_dict=True,
		)
		if allotment.docstatus != 1:
			frappe.throw(_("Allotment {0} must be submitted first.").format(self.tenant_space_allotment))

		self.tenant = allotment.tenant
		self.room = allotment.room
		if not self.monthly_rent:
			self.monthly_rent = allotment.rent_amount

	def validate_duplicate(self):
		existing = frappe.db.get_value(
			"Tenant Rent Invoice",
			{
				"tenant_space_allotment": self.tenant_space_allotment,
				"billing_month": self.billing_month,
				"billing_year": self.billing_year,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(
				_("Rent Invoice {0} already exists for {1} {2}.").format(
					frappe.get_desk_link("Tenant Rent Invoice", existing, show_title_with_name=True),
					self.billing_month,
					self.billing_year,
				),
				frappe.DuplicateEntryError,
			)

	def set_billing_period(self):
		"""Bill only the days the tenant occupied the room in the billing month."""
		month_start = date(int(self.billing_year), MONTHS.index(self.billing_month) + 1, 1)
		month_end = get_last_day(month_start)
		self.total_days = month_end.day

		allotment_date, vacate_date = frappe.db.get_value(
			"Tenant Space Allotment", self.tenant_space_allotment, ["allotment_date", "vacate_date"]
		)
		from_date = max(getdate(allotment_date), month_start)
		to_date = min(getdate(vacate_date), month_end) if vacate_date else month_end

		if to_date < from_date:
			frappe.throw(
				_("Allotment {0} was not active during {1} {2}.").format(
					self.tenant_space_allotment, self.billing_month, self.billing_year
				)
			)

		self.from_date = from_date
		self.to_date = to_date
		# inclusive of both ends: staying 15th to 15th is 1 day
		self.days_stayed = date_diff(to_date, from_date) + 1

	def calculate_totals(self):
		if self.days_stayed == self.total_days:
			self.pro_rated_rent = flt(self.monthly_rent)
		else:
			self.pro_rated_rent = flt(flt(self.monthly_rent) / self.total_days * self.days_stayed)
		self.round_floats_in(self, ["pro_rated_rent"])

		self.total_charges = sum(flt(row.amount) for row in self.charges)
		self.round_floats_in(self, ["total_charges", "discount_amount"])

		self.final_amount = flt(
			self.pro_rated_rent + self.total_charges - flt(self.discount_amount),
			self.precision("final_amount"),
		)
		if self.final_amount < 0:
			frappe.throw(_("Discount cannot be more than the invoice total."))

		self.paid_amount = flt(self.paid_amount) if self.docstatus else 0
		self.outstanding_amount = flt(
			self.final_amount - self.paid_amount, self.precision("outstanding_amount")
		)

	def set_due_date(self):
		if self.due_date:
			if getdate(self.due_date) < getdate(self.posting_date):
				frappe.throw(_("Due Date cannot be before the Posting Date."))
			return

		due_day = frappe.db.get_single_value("Rent Management Settings", "rent_due_day")
		if not due_day:
			self.due_date = self.posting_date
			return

		# due on the given day of the billing month, but never before the posting date
		month_start = getdate(self.from_date).replace(day=1)
		due_date = add_days(month_start, min(due_day, self.total_days) - 1)
		self.due_date = max(getdate(due_date), getdate(self.posting_date))

	def update_paid_amount(self):
		"""Recalculate paid / outstanding amounts from submitted Rent Payments."""
		paid = frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": self.name, "docstatus": 1},
			fields=[{"SUM": "amount", "as": "total"}],
		)[0].total
		self.db_set(
			{
				"paid_amount": flt(paid),
				"outstanding_amount": flt(
					flt(self.final_amount) - flt(paid), self.precision("outstanding_amount")
				),
			}
		)
		self.set_status(update=True)

	def set_status(self, update=False):
		status = get_status(self)
		if update:
			self.db_set("status", status, update_modified=False)
		else:
			self.status = status


def get_status(doc) -> str:
	if doc.docstatus == 0:
		return "Draft"
	if doc.docstatus == 2:
		return "Cancelled"
	if flt(doc.outstanding_amount) <= 0:
		return "Paid"
	if doc.due_date and getdate(doc.due_date) < getdate(nowdate()):
		return "Overdue"
	if flt(doc.paid_amount) > 0:
		return "Partly Paid"
	return "Unpaid"
