# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, cstr, flt, getdate, today

from rent_management.rent_management_system.doctype.tenant_space.tenant_space import (
	get_active_allotments,
	update_room_occupancy,
)


class TenantSpaceAllotment(Document):
	def validate(self):
		self.validate_room_is_free()
		self.set_agreement_terms()
		self.set_defaults_from_room()
		if self.docstatus == 0:
			self.status = "Draft"

	def validate_room_is_free(self):
		room = frappe.db.get_value("Tenant Space", self.room, ["status", "capacity"], as_dict=True)
		if room.status == "Under Renovation":
			frappe.throw(
				_("Room {0} is Under Renovation and cannot be allotted.").format(frappe.bold(self.room))
			)

		capacity = max(cint(room.capacity), 1)
		occupied = get_active_allotments(self.room, exclude=self.name)
		if len(occupied) >= capacity:
			frappe.throw(
				_("Room {0} is full: all {1} bed(s) are allotted ({2}).").format(
					frappe.bold(self.room),
					capacity,
					", ".join(
						frappe.get_desk_link("Tenant Space Allotment", a.name, show_title_with_name=True)
						for a in occupied
					),
				)
			)

		# Tenant is autoincrement-named, so compare names as strings
		if cstr(self.tenant) in [cstr(a.tenant) for a in occupied]:
			frappe.throw(
				_("{0} already stays in room {1}.").format(self.tenant_name or self.tenant, self.room)
			)

		taken = {cint(a.bed_no) for a in occupied}
		if not cint(self.bed_no):
			self.bed_no = next(bed for bed in range(1, capacity + 1) if bed not in taken)
		elif cint(self.bed_no) > capacity:
			frappe.throw(_("Room {0} has only {1} bed(s).").format(self.room, capacity))
		elif cint(self.bed_no) in taken:
			frappe.throw(_("Bed {0} in room {1} is already allotted.").format(self.bed_no, self.room))

	def set_defaults_from_room(self):
		if not self.rent_amount:
			self.rent_amount = frappe.db.get_value("Tenant Space", self.room, "room_rent")

		if not self.security_deposit and self.room_type:
			deposit_applicable, security_deposit = frappe.db.get_value(
				"Tenant Space Type", self.room_type, ["deposit_applicable", "security_deposit"]
			)
			if deposit_applicable:
				self.security_deposit = security_deposit

	def set_agreement_terms(self):
		"""Defaults from Rent Management Settings, and the dates that follow from them."""
		settings = frappe.get_cached_doc("Rent Management Settings")
		for field, default, fallback in (
			("agreement_months", "default_agreement_months", 11),
			("lock_in_months", "default_lock_in_months", 0),
			("notice_period_days", "default_notice_days", 30),
			("rent_increase_percent", "default_rent_increase_percent", 0),
		):
			if self.get(field) in (None, ""):
				value = settings.get(default)
				self.set(field, fallback if value in (None, "") else value)

		start = getdate(self.allotment_date)
		months = cint(self.agreement_months)
		self.agreement_end_date = add_days(add_months(start, months), -1) if months else None
		every = cint(self.rent_increase_every_months) or 12
		self.next_rent_increase_date = add_months(start, every) if flt(self.rent_increase_percent) else None

	def before_update_after_submit(self):
		self.validate_rent_change()

	def validate_rent_change(self):
		before = self.get_doc_before_save()
		if before and flt(before.rent_amount) != flt(self.rent_amount) and not self.flags.revising_rent:
			frappe.throw(_("Use Change Rent to change the rent of an active stay, so the history is kept."))

	@frappe.whitelist()
	def give_notice(self, notice_date=None, vacate_date=None):
		"""The tenant (or landlord) gives notice; the expected move-out follows from the notice period."""
		self.check_permission("write")
		if self.docstatus != 1 or self.status != "Active":
			frappe.throw(_("Only an active stay can be given notice."))
		notice_date = getdate(notice_date or today())
		if notice_date < getdate(self.allotment_date):
			frappe.throw(_("Notice can't be given before the move-in date."))
		expected = (
			getdate(vacate_date) if vacate_date else add_days(notice_date, cint(self.notice_period_days))
		)
		if expected < notice_date:
			frappe.throw(_("The move-out date can't be before the notice date."))
		self.db_set({"notice_given_on": notice_date, "expected_vacate_date": expected})
		lock_in_ends = add_months(getdate(self.allotment_date), cint(self.lock_in_months))
		if cint(self.lock_in_months) and expected < lock_in_ends:
			frappe.msgprint(
				_("The lock-in period runs until {0}. Moving out earlier breaks the agreement.").format(
					frappe.utils.formatdate(lock_in_ends)
				),
				indicator="orange",
				alert=True,
			)
		return {"notice_given_on": notice_date, "expected_vacate_date": expected}

	@frappe.whitelist()
	def withdraw_notice(self):
		self.check_permission("write")
		self.db_set({"notice_given_on": None, "expected_vacate_date": None})

	@frappe.whitelist()
	def revise_rent(self, new_rent, effective_from=None, reason=None):
		"""Change the rent of an active stay from a date, keeping the history."""
		self.check_permission("write")
		new_rent = flt(new_rent)
		if self.docstatus != 1 or self.status != "Active":
			frappe.throw(_("Only an active stay's rent can be changed."))
		if new_rent <= 0:
			frappe.throw(_("Rent must be more than zero."))
		effective_from = getdate(effective_from or today())
		if effective_from < getdate(self.allotment_date):
			frappe.throw(_("The new rent can't start before the move-in date."))
		self.append(
			"rent_revisions",
			{
				"effective_from": effective_from,
				"old_rent": self.get_rent_on(effective_from),
				"new_rent": new_rent,
				"reason": reason,
			},
		)
		self.rent_amount = new_rent
		self.flags.revising_rent = True
		self.save()

	def get_rent_on(self, date) -> float:
		"""Rent for a date: the latest change on or before it, else the rent at move-in."""
		date = getdate(date)
		revisions = sorted(self.get("rent_revisions") or [], key=lambda r: getdate(r.effective_from))
		rent = flt(revisions[0].old_rent) if revisions else flt(self.rent_amount)
		for revision in revisions:
			if getdate(revision.effective_from) <= date:
				rent = flt(revision.new_rent)
		return rent

	def on_submit(self):
		self.db_set("status", "Active")
		update_room_occupancy(self.room)
		frappe.msgprint(
			_("{0} moved into room {1}.").format(self.tenant_name, frappe.bold(self.room)), alert=True
		)

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		update_room_occupancy(self.room)

	@frappe.whitelist()
	def vacate(self, vacate_date=None):
		"""Mark the tenant as moved out and free up their bed."""
		if self.docstatus != 1 or self.status != "Active":
			frappe.throw(_("Only an active allotment can be vacated."))

		vacate_date = getdate(vacate_date or today())
		if vacate_date < getdate(self.allotment_date):
			frappe.throw(_("Vacate Date cannot be before the Allotment Date."))

		self.db_set({"status": "Vacated", "vacate_date": vacate_date, "expected_vacate_date": None})
		update_room_occupancy(self.room)
		frappe.msgprint(
			_("{0} moved out of room {1}.").format(self.tenant_name, frappe.bold(self.room)), alert=True
		)


def apply_rent_increases():
	"""Scheduler (daily): the agreed yearly (or other) rent increase, on its date."""
	from rent_management.subscription import skip_if_lapsed

	if skip_if_lapsed():
		return
	for name in frappe.get_all(
		"Tenant Space Allotment",
		filters=[
			["docstatus", "=", 1],
			["status", "=", "Active"],
			["rent_increase_percent", ">", 0],
			# "<=" alone would also match an empty date (read as 0001-01-01)
			["next_rent_increase_date", "is", "set"],
			["next_rent_increase_date", "<=", today()],
		],
		pluck="name",
	):
		frappe.db.savepoint("rent_increase")
		try:
			allotment = frappe.get_doc("Tenant Space Allotment", name)
			percent = flt(allotment.rent_increase_percent)
			effective = getdate(allotment.next_rent_increase_date)
			new_rent = round(flt(allotment.rent_amount) * (1 + percent / 100))
			allotment.next_rent_increase_date = add_months(
				effective, cint(allotment.rent_increase_every_months) or 12
			)
			allotment.revise_rent(new_rent, effective, _("Agreed increase of {0}%").format(f"{percent:g}"))
		except Exception:
			frappe.db.rollback(save_point="rent_increase")
			frappe.log_error(title=f"Rent increase for {name} failed")


def get_agreement_context(doc) -> dict:
	"""Everything the Rent Agreement print format needs (registered as a Jinja method)."""
	settings = frappe.get_cached_doc("Rent Management Settings")
	tenant = frappe.get_doc("Tenant", doc.tenant)
	room = frappe.get_doc("Tenant Space", doc.room)
	building = frappe.get_doc("Rent Property", room.property)
	address = ", ".join(filter(None, [building.address, building.city, building.state, building.pincode]))
	return {
		"landlord_name": settings.landlord_name or building.property_name,
		"landlord_phone": settings.landlord_phone,
		"landlord_address": settings.landlord_address or address,
		"tenant": tenant,
		"aadhaar": f"XXXX XXXX {tenant.aadhar_last4}" if tenant.aadhar_last4 else None,
		"room": room,
		"building": building,
		"premises_address": address,
		"due_day": cint(settings.rent_due_day),
		"electricity_rate": flt(room.electricity_rate) or flt(settings.electricity_rate)
		if room.has_meter
		else None,
		"terms": settings.agreement_terms,
		"lock_in_ends": add_months(getdate(doc.allotment_date), cint(doc.lock_in_months))
		if cint(doc.lock_in_months)
		else None,
		"money": lambda amount: frappe.utils.fmt_money(
			amount, currency=frappe.db.get_default("currency") or "INR"
		),
	}
