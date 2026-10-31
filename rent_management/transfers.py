# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Room transfers: moving a tenant to another bed or room mid-stay.

The old stay ends the night before the move and a new one starts on the day, so each room is
billed for the nights spent in it. If the old room's bill for that month is already made:

- a draft is re-worked out for the days before the move;
- a submitted one stays as it is, and the new room's bill for the month takes off what the
  old one already charged for the days after the move (so only the difference is paid).

What goes with the tenant: the deposit (still held; a bigger deposit for the new room is
added to its first bill, a smaller one is refunded at move-out), the agreement's term and
renewals, the rest of the lock-in, the rent increase, the meal plan, notice already given,
and the police verification when it's the same building. The updated agreement can be sent
to sign (renewals.py).
"""

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	flt,
	get_first_day,
	get_last_day,
	getdate,
	month_diff,
	nowdate,
)

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

ALLOTMENT = "Tenant Space Allotment"
INVOICE = "Tenant Rent Invoice"
CARRIED = ("notice_period_days", "rent_increase_percent", "rent_increase_every_months", "meal_plan",
	"meal_charge", "refund_upi_id", "refund_bank_details")  # fmt: skip
VERIFICATION = ("police_verification", "verification_submitted_on", "police_station", "verification_reference",
	"verified_on", "verification_acknowledgement", "verification_copy", "verification_note")  # fmt: skip


def room_deposit(room) -> float:
	room_type = frappe.db.get_value("Tenant Space", room, "room_type")
	if not room_type:
		return 0
	applicable, deposit = frappe.db.get_value(
		"Tenant Space Type", room_type, ["deposit_applicable", "security_deposit"]
	)
	return flt(deposit) if applicable else 0


def free_beds(room) -> list[int]:
	capacity = max(cint(frappe.db.get_value("Tenant Space", room, "capacity")), 1)
	taken = {
		cint(b)
		for b in frappe.get_all(
			ALLOTMENT, filters={"room": room, "docstatus": 1, "status": "Active"}, pluck="bed_no"
		)
	}
	return [b for b in range(1, capacity + 1) if b not in taken]


def options(allotment) -> dict:
	"""For the dialog: rooms with a free bed, their rent and deposit."""
	stay = frappe.get_doc(ALLOTMENT, allotment)
	rooms = []
	for r in frappe.get_all(
		"Tenant Space",
		filters={"status": ("!=", "Under Renovation")},
		fields=["name", "room_number", "property", "room_rent", "capacity", "floor"],
		order_by="property asc, room_number asc",
	):
		beds = free_beds(r.name)
		if beds:
			rooms.append({**r, "free_beds": beds, "deposit": room_deposit(r.name)})
	return {
		"stay": {
			"name": stay.name,
			"room": stay.room,
			"room_number": frappe.db.get_value("Tenant Space", stay.room, "room_number"),
			"property": stay.property,
			"rent": flt(stay.rent_amount),
			"deposit": flt(stay.security_deposit),
			"deposit_collected": cint(stay.deposit_collected),
			"since": stay.allotment_date,
		},
		"rooms": rooms,
		"today": nowdate(),
	}


def validate(stay, room, on):
	if stay.docstatus != 1 or stay.status != "Active":
		frappe.throw(_("Only an active stay can move to another room."))
	if on > getdate(nowdate()):
		frappe.throw(_("Record the move on the day it happens, or after."))
	if on <= getdate(stay.allotment_date):
		frappe.throw(_("The move has to be after the move-in date ({0}).").format(frappe.utils.formatdate(stay.allotment_date)))  # fmt: skip
	later = frappe.get_all(
		INVOICE,
		filters={
			"tenant_space_allotment": stay.name,
			"docstatus": ("<", 2),
			"from_date": (">", get_last_day(on)),
		},
		pluck="name",
	)
	if later:
		frappe.throw(_("Bills after the move's month already exist for the old room ({0}). Cancel them first.").format(", ".join(later)))  # fmt: skip
	if frappe.db.exists(ALLOTMENT, {"tenant": stay.tenant, "docstatus": 0}):
		frappe.throw(_("{0} has a draft stay. Submit or delete it first.").format(stay.tenant_name))


def transfer(allotment, room, bed_no=None, transfer_date=None, new_rent=None, new_deposit=None, send_for_signing=0) -> dict:  # fmt: skip
	from rent_management import activity, renewals

	old = frappe.get_doc(ALLOTMENT, allotment)
	old.check_permission("write")
	on = getdate(transfer_date or nowdate())
	validate(old, room, on)
	beds = free_beds(room)
	bed_no = cint(bed_no) or (beds[0] if beds else 0)
	if room != old.room and bed_no not in beds:
		frappe.throw(_("Bed {0} in that room isn't free.").format(bed_no))
	if room == old.room and bed_no == cint(old.bed_no):
		frappe.throw(_("Choose another bed or room."))

	rent = (
		flt(new_rent) or flt(frappe.db.get_value("Tenant Space", room, "room_rent")) or flt(old.rent_amount)
	)
	held = flt(old.security_deposit)
	wanted = flt(new_deposit) if new_deposit not in (None, "") else (room_deposit(room) or held)
	top_up = max(flt(wanted - held, 2), 0) if cint(old.deposit_collected) else 0
	deposit = max(wanted, held)  # a smaller deposit: the rest is refunded at move-out

	# the old stay ends the night before
	old.vacate(add_days(on, -1))
	same_building = frappe.db.get_value("Tenant Space", room, "property") == old.property
	months_in = month_diff(on, old.allotment_date) - 1
	new = frappe.get_doc(
		{
			"doctype": ALLOTMENT,
			"tenant": old.tenant,
			"room": room,
			"bed_no": bed_no,
			"allotment_date": on,
			"rent_amount": rent,
			"security_deposit": deposit,
			"deposit_collected": old.deposit_collected,
			"deposit_collected_on": old.deposit_collected_on,
			"agreement_months": old.agreement_months,
			"lock_in_months": max(cint(old.lock_in_months) - max(months_in, 0), 0),
			"transferred_from": old.name,
			**{f: old.get(f) for f in CARRIED},
			**({f: old.get(f) for f in VERIFICATION} if same_building else {}),
		}
	)
	new.flags.transferring = True
	new.insert()
	new.submit()
	new.db_set(
		{
			# the same agreement goes on: its term, renewals and next increase
			"agreement_start_date": old.agreement_start_date or old.allotment_date,
			"agreement_end_date": old.agreement_end_date,
			"renewals": old.renewals,
			"renewed_on": old.renewed_on,
			"next_rent_increase_date": old.next_rent_increase_date,
			"notice_given_on": old.notice_given_on,
			"expected_vacate_date": old.expected_vacate_date,
		}
	)
	old.db_set("transferred_to", new.name)

	bill = rebill(old, new, on, top_up)
	activity.log(
		"Stays",
		_("moved {0} from room {1} to room {2}").format(old.tenant_name, old.room, room),
		new,
		rent,
	)
	result = {"stay": new.name, "room": room, "bed_no": bed_no, "rent": rent, "deposit": deposit, "top_up": top_up,
		"bill": bill, "refund_later": max(flt(held - wanted, 2), 0)}  # fmt: skip
	if cint(send_for_signing):
		result["signing"] = renewals.send_for_signing_now(new.name, purpose="Room Change")
	return result


def rebill(old, new, on, top_up) -> str | None:
	"""The move's month: each room billed for its nights. Returns the new room's bill, if made now."""
	month, year = MONTHS[on.month - 1], on.year
	old_bill = frappe.db.get_value(
		INVOICE, {"tenant_space_allotment": old.name, "billing_month": month, "billing_year": year, "docstatus": ("<", 2)},
		["name", "docstatus"], as_dict=True,
	)  # fmt: skip
	charges = []
	submit = False
	if old_bill and old_bill.docstatus == 0:
		frappe.get_doc(INVOICE, old_bill.name).save()  # re-worked out for the nights before the move
	elif old_bill:
		inv = frappe.get_doc(INVOICE, old_bill.name)
		days = date_diff(inv.to_date, on) + 1
		if days > 0:
			already = flt(flt(inv.monthly_rent) / inv.total_days * days, 2)
			charges.append({"charge_type": "Other", "amount": -already,
				"description": _("Room {0} rent already billed for {1} days").format(old.room, days)[:140]})  # fmt: skip
		submit = True
	if top_up:
		charges.append({"charge_type": "Other", "amount": top_up,
			"description": _("Deposit top-up for room {0}").format(new.room)})  # fmt: skip
	if not (old_bill or top_up):
		return None  # this month's bills aren't made yet: both rooms are billed then
	doc = frappe.get_doc(
		{
			"doctype": INVOICE,
			"tenant_space_allotment": new.name,
			"billing_month": month,
			"billing_year": year,
			"posting_date": max(get_first_day(on), getdate(nowdate())),
			"charges": [],
		}
	)
	doc.flags.skip_meter_charges = True  # the room's electricity is shared when it's next read
	doc.flags.skip_referral_credits = True
	doc.insert()
	if charges:
		for c in charges:
			doc.append("charges", c)
		# a cheaper room: the credit can't be more than the new room's rent
		total = flt(doc.pro_rated_rent) + sum(flt(c["amount"]) for c in charges)
		if total < 0:
			doc.charges[0].amount = flt(doc.charges[0].amount - total, 2)
		doc.save()
	if submit:
		doc.submit()
	return doc.name
