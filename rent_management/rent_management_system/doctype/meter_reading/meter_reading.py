# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, flt, getdate


class MeterReading(Document):
	def validate(self):
		self.validate_not_billed()
		self.validate_unique_date()
		self.set_previous_reading()
		self.calculate_amount()
		self.split_between_tenants()
		self.status = get_status(self)

	def on_trash(self):
		self.validate_not_billed(deleting=True)
		later = frappe.db.exists(
			"Meter Reading",
			{"room": self.room, "reading_date": (">", self.reading_date), "name": ("!=", self.name)},
		)
		if later:
			frappe.throw(_("Delete the later readings of room {0} first.").format(self.room))

	def validate_not_billed(self, deleting=False):
		before = self.get_doc_before_save() if not self.is_new() else None
		billed = [s.rent_invoice for s in (before or self).shares if s.rent_invoice]
		if billed and (deleting or self.has_reading_changed(before)):
			frappe.throw(
				_("This reading is already billed in {0}. Remove it from those invoices first.").format(
					", ".join(sorted(set(billed)))
				)
			)

	def has_reading_changed(self, before) -> bool:
		if not before:
			return True
		fields = ("room", "reading_date", "reading", "meter_replaced", "rate")
		return any(str(before.get(f)) != str(self.get(f)) for f in fields)

	def validate_unique_date(self):
		if frappe.db.exists(
			"Meter Reading", {"room": self.room, "reading_date": self.reading_date, "name": ("!=", self.name)}
		):
			frappe.throw(
				_("Room {0} already has a reading on {1}.").format(
					self.room, frappe.utils.formatdate(self.reading_date)
				)
			)
		if not frappe.db.get_value("Tenant Space", self.room, "has_meter"):
			frappe.throw(
				_("Room {0} has no electricity meter. Tick Has Electricity Meter on the room first.").format(
					self.room
				)
			)

	def set_previous_reading(self):
		previous = frappe.get_all(
			"Meter Reading",
			filters={"room": self.room, "reading_date": ("<", self.reading_date), "name": ("!=", self.name)},
			fields=["reading", "reading_date"],
			order_by="reading_date desc",
			limit=1,
		)
		later = frappe.db.exists(
			"Meter Reading",
			{"room": self.room, "reading_date": (">", self.reading_date), "name": ("!=", self.name)},
		)
		if later and self.is_new():
			frappe.throw(
				_("Room {0} has a later reading. Readings are entered in date order.").format(self.room)
			)
		if previous:
			self.previous_reading = previous[0].reading
			self.previous_reading_date = previous[0].reading_date
		else:
			self.previous_reading = None
			self.previous_reading_date = None

	def calculate_amount(self):
		if self.previous_reading_date is None:
			self.units = 0  # opening reading: nothing to bill yet
		elif cint(self.meter_replaced):
			self.units = flt(self.reading)
		else:
			if flt(self.reading) < flt(self.previous_reading):
				frappe.throw(
					_(
						"Lower than the previous reading {0}. Tick New Meter if the meter was replaced."
					).format(f"{flt(self.previous_reading):g}")
				)
			self.units = flt(self.reading) - flt(self.previous_reading)

		if not self.rate:
			self.rate = frappe.db.get_value(
				"Tenant Space", self.room, "electricity_rate"
			) or frappe.db.get_single_value("Rent Management Settings", "electricity_rate")
		self.amount = flt(flt(self.units) * flt(self.rate), self.precision("amount"))

	def split_between_tenants(self):
		"""Share the units between the tenants who stayed since the previous reading, by days."""
		billed = {s.tenant_space_allotment: s.rent_invoice for s in self.shares if s.rent_invoice}
		self.set("shares", [])
		if not self.previous_reading_date or not flt(self.units):
			return

		start = add_days(self.previous_reading_date, 1)
		end = getdate(self.reading_date)
		stays = []
		for a in frappe.get_all(
			"Tenant Space Allotment",
			filters={
				"room": self.room,
				"docstatus": 1,
				"status": ("in", ("Active", "Vacated")),
				"allotment_date": ("<=", end),
			},
			or_filters=[["vacate_date", "is", "not set"], ["vacate_date", ">=", start]],
			fields=["name", "tenant", "tenant_name", "allotment_date", "vacate_date"],
			order_by="allotment_date asc",
		):
			days = (
				date_diff(
					min(getdate(a.vacate_date) if a.vacate_date else end, end),
					max(getdate(a.allotment_date), getdate(start)),
				)
				+ 1
			)
			if days > 0:
				stays.append((a, days))

		total_days = sum(days for _a, days in stays)
		if not total_days:
			return  # the room was empty: the landlord bears it
		allocated_units = allocated_amount = 0
		for i, (a, days) in enumerate(stays):
			last = i == len(stays) - 1
			units = flt(self.units) - allocated_units if last else flt(flt(self.units) * days / total_days, 2)
			amount = (
				flt(self.amount) - allocated_amount
				if last
				else flt(flt(self.amount) * days / total_days, self.precision("amount"))
			)
			allocated_units += units
			allocated_amount += amount
			self.append(
				"shares",
				{
					"tenant_space_allotment": a.name,
					"tenant": a.tenant,
					"tenant_name": a.tenant_name,
					"days": days,
					"units": flt(units, 2),
					"amount": amount,
					"rent_invoice": billed.get(a.name),
				},
			)


def get_status(doc) -> str:
	if doc.previous_reading_date is None:
		return "Opening"
	if not doc.shares:
		return "Not Billable"
	billed = sum(1 for s in doc.shares if s.rent_invoice)
	if not billed:
		return "Unbilled"
	return "Billed" if billed == len(doc.shares) else "Partly Billed"


def update_status(reading_name: str):
	doc = frappe.get_doc("Meter Reading", reading_name)
	doc.db_set("status", get_status(doc), update_modified=False)


# ---------------------------------------------------------------- invoices


def num(value) -> str:
	"""1287.0 -> 1287, 12.5 -> 12.5"""
	return f"{flt(value, 2):g}"


def get_unbilled_shares(allotment: str, up_to=None) -> list:
	share = frappe.qb.DocType("Meter Reading Share")
	reading = frappe.qb.DocType("Meter Reading")
	query = (
		frappe.qb.from_(share)
		.join(reading)
		.on(share.parent == reading.name)
		.select(
			share.name,
			share.parent.as_("meter_reading"),
			share.units,
			share.amount,
			share.days,
			reading.previous_reading,
			reading.reading,
			reading.units.as_("total_units"),
			reading.rate,
			reading.reading_date,
		)
		.where(share.parenttype == "Meter Reading")
		.where(share.tenant_space_allotment == allotment)
		.where((share.rent_invoice.isnull()) | (share.rent_invoice == ""))
		.orderby(reading.reading_date)
	)
	if up_to:
		query = query.where(reading.reading_date <= up_to)
	return query.run(as_dict=True)


def add_meter_charges(invoice):
	"""Add the tenant's unbilled electricity to a new or draft rent invoice."""
	already = {row.meter_reading_share for row in invoice.charges if row.meter_reading_share}
	for share in get_unbilled_shares(invoice.tenant_space_allotment, up_to=invoice.posting_date):
		if share.name in already or not flt(share.amount):
			continue
		if flt(share.units) == flt(share.total_units):
			detail = _("Meter {0} to {1}: {2} units at {3}").format(
				num(share.previous_reading), num(share.reading), num(share.units), num(share.rate)
			)
		else:
			detail = _("{0} of {1} units (meter {2} to {3}) at {4}").format(
				num(share.units),
				num(share.total_units),
				num(share.previous_reading),
				num(share.reading),
				num(share.rate),
			)
		invoice.append(
			"charges",
			{
				"charge_type": "Electricity",
				"description": detail[:140],
				"amount": share.amount,
				"meter_reading": share.meter_reading,
				"meter_reading_share": share.name,
			},
		)


def link_meter_charges(invoice):
	"""Mark the shares on an invoice as billed in it, and free the ones removed from it."""
	on_invoice = {row.meter_reading_share for row in invoice.charges if row.meter_reading_share}
	if invoice.docstatus == 2:
		on_invoice = set()
	readings = set()
	for name, parent in frappe.get_all(
		"Meter Reading Share",
		filters={"rent_invoice": invoice.name, "parenttype": "Meter Reading"},
		fields=["name", "parent"],
		as_list=True,
	):
		if name not in on_invoice:
			frappe.db.set_value("Meter Reading Share", name, "rent_invoice", None, update_modified=False)
			readings.add(parent)
	for name in on_invoice:
		parent = frappe.db.get_value("Meter Reading Share", name, "parent")
		frappe.db.set_value("Meter Reading Share", name, "rent_invoice", invoice.name, update_modified=False)
		readings.add(parent)
	for reading in readings:
		update_status(reading)


def unlink_meter_charges(invoice):
	for name, parent in frappe.get_all(
		"Meter Reading Share",
		filters={"rent_invoice": invoice.name, "parenttype": "Meter Reading"},
		fields=["name", "parent"],
		as_list=True,
	):
		frappe.db.set_value("Meter Reading Share", name, "rent_invoice", None, update_modified=False)
		update_status(parent)
