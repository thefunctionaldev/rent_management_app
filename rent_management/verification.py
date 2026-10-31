# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Police verification of tenants: tracking that each one is done.

Many cities ask landlords to submit a verification form for every tenant to the local police
station, within some days of the move-in. With tracking on (Settings), every new stay starts
as Pending; a manager (or warden) marks it Submitted (date, police station, acknowledgement
number, a photo of the acknowledgement) and then Verified (date, the stamped copy), or Not
Required. Managers and wardens are told when one falls due, and every Monday what's pending.

The form itself is the Tenant Verification Form print (checkin.py).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate

ALLOTMENT = "Tenant Space Allotment"
SETTINGS = "Rent Management Settings"
STATUSES = ("Pending", "Submitted", "Verified", "Not Required")


def enabled() -> bool:
	return bool(cint(frappe.db.get_single_value(SETTINGS, "police_verification_enabled")))


def due_days() -> int:
	return cint(frappe.db.get_single_value(SETTINGS, "police_verification_days")) or 7


def on_move_in(doc, method=None):
	"""Tenant Space Allotment on_submit: a new stay to verify."""
	if enabled() and not doc.police_verification:
		station = frappe.db.get_value("Rent Property", doc.property, "police_station")
		doc.db_set({"police_verification": "Pending", "police_station": station}, update_modified=False)


def due_on(stay) -> str:
	return str(add_days(stay.allotment_date, due_days()))


def get_verifications(property=None) -> dict:
	filters = {"docstatus": 1, "police_verification": ("is", "set")}
	if property:
		filters["property"] = property
	rows = frappe.get_all(
		ALLOTMENT,
		filters=filters,
		fields=["name", "tenant", "tenant_name", "room", "property", "allotment_date", "status", "police_verification",
			"verification_submitted_on", "police_station", "verification_reference", "verified_on",
			"verification_acknowledgement", "verification_copy", "verification_note"],
		order_by="allotment_date desc",
	)  # fmt: skip
	today = getdate(nowdate())
	groups = {"overdue": [], "pending": [], "submitted": [], "done": []}
	for row in rows:
		row.due_on = due_on(row)
		row.days_overdue = max(date_diff(today, row.due_on), 0)
		if row.police_verification == "Pending":
			if row.status != "Active":
				continue  # moved out before it was done
			groups["overdue" if row.days_overdue else "pending"].append(row)
		elif row.police_verification == "Submitted":
			row.waiting_days = (
				date_diff(today, row.verification_submitted_on) if row.verification_submitted_on else None
			)
			groups["submitted"].append(row)
		else:
			groups["done"].append(row)
	groups["done"] = groups["done"][:50]
	untracked = frappe.db.count(
		ALLOTMENT,
		{
			"docstatus": 1,
			"status": "Active",
			"police_verification": ("is", "not set"),
			**({"property": property} if property else {}),
		},
	)
	return {**groups, "enabled": enabled(), "due_days": due_days(), "untracked": untracked}


def update(allotment, data):
	"""Mark a stay's verification: {status, submitted_on, police_station, reference, verified_on,
	note, acknowledgement, copy} (acknowledgement/copy are data URLs of a photo or PDF)."""
	from rent_management import activity, pictures

	data = frappe.parse_json(data)
	doc = frappe.get_doc(ALLOTMENT, allotment)
	doc.check_permission("write")
	status = data.get("status")
	if status not in STATUSES:
		frappe.throw(_("Choose what happened with the verification."))
	values = {"police_verification": status, "verification_note": (data.get("note") or "").strip() or None}
	if status in ("Submitted", "Verified"):
		values.update(
			{
				"verification_submitted_on": data.get("submitted_on")
				or doc.verification_submitted_on
				or nowdate(),
				"police_station": (data.get("police_station") or doc.police_station or "").strip() or None,
				"verification_reference": (data.get("reference") or doc.verification_reference or "").strip()
				or None,
			}
		)
	if status == "Verified":
		values["verified_on"] = data.get("verified_on") or doc.verified_on or nowdate()
	elif status in ("Pending", "Submitted"):
		values["verified_on"] = None
	for field in ("verification_submitted_on", "verified_on"):
		if values.get(field) and getdate(values[field]) > getdate(nowdate()):
			frappe.throw(_("Dates can't be in the future."))
	doc.db_set(values)
	pictures.set_document(
		doc,
		"verification_acknowledgement",
		data.get("acknowledgement"),
		f"verification-acknowledgement-{doc.tenant_name}",
	)
	pictures.set_document(doc, "verification_copy", data.get("copy"), f"verification-{doc.tenant_name}")
	activity.log(
		"Stays",
		{
			"Pending": _("marked the police verification of {0} as pending"),
			"Submitted": _("submitted the police verification of {0}"),
			"Verified": _("noted that the police verified {0}"),
			"Not Required": _("marked the police verification of {0} as not needed"),
		}[status].format(doc.tenant_name),
		doc,
	)


def track(allotment):
	"""Start tracking a stay that moved in before tracking was turned on."""
	doc = frappe.get_doc(ALLOTMENT, allotment)
	doc.check_permission("write")
	if not doc.police_verification:
		doc.db_set(
			{
				"police_verification": "Pending",
				"police_station": frappe.db.get_value("Rent Property", doc.property, "police_station"),
			}
		)


def remind():
	"""Daily: managers and wardens hear when a verification falls due; Mondays, what's pending."""
	if not enabled():
		return
	from rent_management.portal import notify_managers

	data = get_verifications()
	today = getdate(nowdate())
	due_today = [r for r in data["pending"] + data["overdue"] if getdate(r.due_on) == today]
	for row in due_today:
		notify_managers(
			_("Police verification due for {0}").format(row.tenant_name),
			_("{0} (room {1}) moved in on {2}. Submit their verification form today.").format(
				row.tenant_name, row.room, frappe.utils.formatdate(row.allotment_date)
			),
			link="/rent/verification",
			area="rooms",
			property=row.property,
		)
	if today.weekday() == 0 and (data["overdue"] or data["submitted"]):
		notify_managers(
			_("Police verification: {0} overdue, {1} waiting").format(
				len(data["overdue"]), len(data["submitted"])
			),
			_("{0} still to submit, {1} submitted and waiting for the police.").format(
				len(data["overdue"]), len(data["submitted"])
			),
			link="/rent/verification",
			area="rooms",
		)
