# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The hostel register: night attendance, leave and visitors.

- Leave: tenants ask from the tenant app (or the manager adds it); once approved, the days
  are marked On Leave at night attendance and their meals are skipped, so the kitchen
  doesn't cook for them.
- Night attendance: each night the warden marks every tenant present, late or absent.
  Absent without leave stands out, with their emergency contact.
- Visitors: checked in and out at the gate, with who they visit; tenants can tell the
  warden in advance who is coming.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, get_time, getdate, now_datetime, nowdate

from rent_management import mess

LEAVE = "Tenant Leave"
ATTENDANCE = "Night Attendance"
VISITOR = "Visitor Log"
STATUSES = ("Present", "Late", "Absent", "On Leave")


# ---------------------------------------------------------------- leave


def request_leave(allotment, from_date, to_date, destination=None, reason=None, source="Tenant App") -> str:
	stay = frappe.get_doc("Tenant Space Allotment", allotment)
	if stay.docstatus != 1 or stay.status != "Active":
		frappe.throw(_("Only a current stay can have leave."))
	if source == "Tenant App" and getdate(to_date) < getdate(nowdate()):
		frappe.throw(_("Choose days from today on."))
	doc = frappe.get_doc(
		{
			"doctype": LEAVE,
			"allotment": allotment,
			"from_date": from_date,
			"to_date": to_date,
			"destination": (destination or "").strip()[:140] or None,
			"reason": (reason or "").strip()[:500] or None,
			"source": source,
			"status": "Approved" if source == "Manager" else "Requested",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	if doc.status == "Approved":
		doc.db_set("decided_by", frappe.session.user)
		skip_meals(doc)
	elif source == "Tenant App":
		from rent_management.portal import notify_managers

		notify_managers(
			_("{0} asked for leave").format(doc.tenant_name),
			_("{0} (room {1}) is away from {2} to {3}{4}. Approve it in Register.").format(
				doc.tenant_name,
				doc.room,
				frappe.utils.formatdate(doc.from_date),
				frappe.utils.formatdate(doc.to_date),
				f", going to {doc.destination}" if doc.destination else "",
			),
			link="/rent/register?tab=leave",
		)
	return doc.name


def decide_leave(name, approve, note=None):
	doc = frappe.get_doc(LEAVE, name)
	if doc.status not in ("Requested", "Approved", "Rejected"):
		frappe.throw(_("This leave was cancelled."))
	doc.update(
		{
			"status": "Approved" if cint(approve) else "Rejected",
			"decided_by": frappe.session.user,
			"decision_note": note,
		}
	)
	doc.save()
	unskip_meals(doc)
	if doc.status == "Approved":
		skip_meals(doc)


def cancel_leave(name):
	doc = frappe.get_doc(LEAVE, name)
	doc.db_set("status", "Cancelled")
	unskip_meals(doc)


def skip_meals(leave):
	"""Approved leave: their meals on those days aren't cooked (from today on)."""
	stay = frappe.db.get_value(
		"Tenant Space Allotment", leave.allotment, ["meal_plan", "property"], as_dict=True
	)
	if not stay.meal_plan:
		return
	meals = [m["meal"] for m in mess.meals_of(stay.property)]
	day = max(getdate(leave.from_date), getdate(nowdate()))
	while day <= getdate(leave.to_date):
		for meal in meals:
			if not frappe.db.exists(mess.OPTOUT, {"allotment": leave.allotment, "date": day, "meal": meal}):
				frappe.get_doc(
					{
						"doctype": mess.OPTOUT,
						"allotment": leave.allotment,
						"date": day,
						"meal": meal,
						"source": "Leave",
						"leave": leave.name,
					}
				).insert(ignore_permissions=True)
		day = add_days(day, 1)


def unskip_meals(leave):
	for name in frappe.get_all(
		mess.OPTOUT, filters={"leave": leave.name, "date": (">=", nowdate())}, pluck="name"
	):
		frappe.delete_doc(mess.OPTOUT, name, ignore_permissions=True)


def leave_on(property, day) -> dict:
	"""{allotment: leave} for approved leave covering the day."""
	return {
		row.allotment: row
		for row in frappe.get_all(
			LEAVE,
			filters={
				"property": property,
				"status": "Approved",
				"from_date": ("<=", getdate(day)),
				"to_date": (">=", getdate(day)),
			},
			fields=["name", "allotment", "to_date", "destination"],
		)
	}


def get_leaves(property=None) -> dict:
	filters = {"property": property} if property else {}
	rows = frappe.get_all(
		LEAVE,
		filters={**filters, "to_date": (">=", add_days(nowdate(), -30))},
		fields=[
			"name",
			"tenant",
			"tenant_name",
			"room",
			"property",
			"from_date",
			"to_date",
			"status",
			"destination",
			"reason",
			"source",
			"decision_note",
		],
		order_by="from_date desc",
	)
	today = getdate(nowdate())
	return {
		"requested": [r for r in rows if r.status == "Requested"],
		"away": [r for r in rows if r.status == "Approved" and r.from_date <= today <= r.to_date],
		"upcoming": [r for r in rows if r.status == "Approved" and r.from_date > today],
		"recent": [
			r for r in rows if r.status in ("Approved", "Rejected", "Cancelled") and r.to_date < today
		][:30],
	}


# ---------------------------------------------------------------- night attendance


def get_attendance(property, day=None) -> dict:
	"""The night's list: every tenant staying, with what was marked (or On Leave)."""
	day = getdate(day or nowdate())
	stays = frappe.get_all(
		"Tenant Space Allotment",
		filters={
			"docstatus": 1,
			"property": property,
			"allotment_date": ("<=", day),
			"status": ("in", ("Active", "Vacated")),
		},
		or_filters=[["vacate_date", "is", "not set"], ["vacate_date", ">", day]],
		fields=["name", "tenant", "tenant_name", "room", "bed_no"],
		order_by="room asc, bed_no asc",
	)
	name = frappe.db.get_value(ATTENDANCE, {"property": property, "date": day})
	marked = {}
	if name:
		marked = {r.allotment: r for r in frappe.get_doc(ATTENDANCE, name).entries}
	away = leave_on(property, day)
	contacts = {
		str(t.name): t
		for t in frappe.get_all(
			"Tenant",
			filters={"name": ("in", [s.tenant for s in stays] or [""])},
			fields=[
				"name",
				"mobile_no",
				"display_picture",
				"emergency_contact_name",
				"emergency_contact_relation",
				"emergency_contact_phone",
			],
		)
	}
	rows = []
	for stay in stays:
		entry = marked.get(stay.name)
		tenant = contacts.get(str(stay.tenant)) or frappe._dict()
		rows.append(
			{
				"allotment": stay.name,
				"tenant": stay.tenant,
				"tenant_name": stay.tenant_name,
				"room": stay.room,
				"bed_no": stay.bed_no,
				"status": (entry.status if entry and entry.status else None)
				or ("On Leave" if stay.name in away else None),
				"note": entry.note if entry else None,
				"on_leave": stay.name in away,
				"leave_until": away[stay.name].to_date if stay.name in away else None,
				"mobile_no": tenant.mobile_no,
				"picture": tenant.display_picture,
				"emergency": {
					"name": tenant.emergency_contact_name,
					"relation": tenant.emergency_contact_relation,
					"phone": tenant.emergency_contact_phone,
				},
			}
		)
	curfew = frappe.db.get_value("Rent Property", property, "curfew_time")
	return {
		"date": str(day),
		"taken": bool(name),
		"curfew": str(curfew)[:5] if curfew else None,
		"rows": rows,
		"history": attendance_history(property),
	}


def save_attendance(property, day, entries) -> str:
	day = getdate(day)
	if day > getdate(nowdate()):
		frappe.throw(_("Attendance can't be taken for a night that hasn't come."))
	entries = frappe.parse_json(entries) or []
	name = frappe.db.get_value(ATTENDANCE, {"property": property, "date": day})
	doc = frappe.get_doc(ATTENDANCE, name) if name else frappe.new_doc(ATTENDANCE)
	doc.update({"property": property, "date": day})
	names = frappe._dict(
		(s.name, s)
		for s in frappe.get_all(
			"Tenant Space Allotment",
			filters={"name": ("in", [e.get("allotment") for e in entries] or [""]), "property": property},
			fields=["name", "tenant", "tenant_name", "room"],
		)
	)
	doc.set("entries", [])
	for entry in entries:
		stay = names.get(entry.get("allotment"))
		if not stay:
			continue
		doc.append(
			"entries",
			{
				"allotment": stay.name,
				"tenant": stay.tenant,
				"tenant_name": stay.tenant_name,
				"room": stay.room,
				"status": entry.get("status") if entry.get("status") in STATUSES else None,
				"note": (entry.get("note") or "")[:140] or None,
			},
		)
	doc.save()
	return doc.name


def attendance_history(property, nights=14) -> list:
	return frappe.get_all(
		ATTENDANCE,
		filters={"property": property, "date": (">=", add_days(nowdate(), -nights))},
		fields=["name", "date", "present", "late", "absent", "on_leave"],
		order_by="date desc",
	)


# ---------------------------------------------------------------- visitors


def get_visitors(property=None) -> dict:
	filters = {"property": property} if property else {}
	fields = [
		"name",
		"property",
		"visitor_name",
		"visitor_phone",
		"purpose",
		"tenant",
		"tenant_name",
		"status",
		"expected_on",
		"check_in",
		"check_out",
		"overnight",
		"source",
	]
	today = getdate(nowdate())

	def visitors(extra, order_by="check_in desc", limit=None):
		rows = frappe.get_all(
			VISITOR, filters={**filters, **extra}, fields=fields, order_by=order_by, limit=limit
		)
		for row in rows:
			row.after_hours = after_hours(row)
		return rows

	return {
		"inside": visitors({"status": "Inside"}),
		"expected": visitors({"status": "Expected", "expected_on": (">=", today)}, "expected_on asc"),
		"today": visitors({"status": "Left", "check_in": (">=", today)}),
		"recent": visitors(
			{"status": "Left", "check_in": ("between", (add_days(today, -14), add_days(today, -1)))}, limit=50
		),
	}


def after_hours(visitor) -> bool:
	"""Came in after visiting hours (and didn't say they were staying overnight)."""
	until = frappe.get_cached_value("Rent Property", visitor.property, "visitors_until")
	if not (until and visitor.check_in) or visitor.overnight:
		return False
	return get_datetime(visitor.check_in).time() > get_time(until)


def check_in(data) -> str:
	"""A visitor at the gate: new, or one a tenant said was coming."""
	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc(VISITOR, data["name"])
	else:
		doc = frappe.new_doc(VISITOR)
		doc.update(
			{
				field: data.get(field)
				for field in ("property", "visitor_name", "visitor_phone", "purpose", "tenant", "overnight")
			}
		)
		doc.source = "Manager"
		if not doc.property and doc.tenant:
			doc.property = frappe.db.get_value(
				"Tenant Space Allotment",
				{"tenant": doc.tenant, "docstatus": 1, "status": "Active"},
				"property",
			)
	doc.update({"status": "Inside", "check_in": now_datetime(), "check_out": None})
	doc.save()
	return doc.name


def check_out(name):
	doc = frappe.get_doc(VISITOR, name)
	doc.update({"status": "Left", "check_out": now_datetime()})
	doc.save()


def expect_visitor(
	tenant, stay, visitor_name, expected_on, visitor_phone=None, purpose=None, overnight=0
) -> str:
	"""A tenant tells the warden someone is coming (from the tenant app)."""
	if getdate(expected_on) < getdate(nowdate()):
		frappe.throw(_("Choose today or a later day."))
	doc = frappe.get_doc(
		{
			"doctype": VISITOR,
			"property": stay.property,
			"tenant": tenant,
			"visitor_name": (visitor_name or "").strip()[:140],
			"visitor_phone": (visitor_phone or "").strip()[:20] or None,
			"purpose": (purpose or "").strip()[:140] or None,
			"expected_on": expected_on,
			"overnight": cint(overnight),
			"status": "Expected",
			"source": "Tenant App",
		}
	)
	if not doc.visitor_name:
		frappe.throw(_("Enter your visitor's name."))
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def summary(property=None) -> dict:
	"""For the dashboard: what needs a look."""
	filters = {"property": property} if property else {}
	return {
		"leave_requests": frappe.db.count(LEAVE, {**filters, "status": "Requested"}),
		"visitors_inside": frappe.db.count(VISITOR, {**filters, "status": "Inside"}),
	}
