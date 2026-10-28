# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The owner's monthly summary: how last month went, in one message.

The Monthly report page shows it for any month, with a button to open it in WhatsApp (no
WhatsApp account needed). If turned on in Settings, it is also sent to the owner on a day
of each month, on WhatsApp (template below) and by email.

	rent_owner_summary  Hello {{1}}, here is {{2}} at {{3}}: {{4}} collected of {{5}} invoiced,
	                    {{6}} spent, {{7}} profit. {{8}} of {{9}} beds taken. {{10}} still to collect. {{11}}
"""

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	add_months,
	cint,
	flt,
	get_first_day,
	get_last_day,
	get_url,
	getdate,
	nowdate,
)

from rent_management import notifications, profit
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

SETTINGS = "Rent Management Settings"
ALLOTMENT = "Tenant Space Allotment"
INVOICE = "Tenant Rent Invoice"


def last_month():
	day = add_months(getdate(nowdate()), -1)
	return MONTHS[day.month - 1], day.year


def staying_on(day, property=None) -> list:
	filters = {"docstatus": 1, "allotment_date": ("<=", day), "status": ("in", ("Active", "Vacated"))}
	if property:
		filters["property"] = property
	return frappe.get_all(
		ALLOTMENT,
		filters=filters,
		or_filters=[["vacate_date", "is", "not set"], ["vacate_date", ">", day]],
		fields=["name", "property", "room"],
	)


def beds(property=None) -> dict:
	active = frappe.get_all("Rent Property", filters={"is_active": 1}, pluck="name")
	filters = {"property": ("in", [property] if property else active or [""])}
	totals = {}
	for room in frappe.get_all("Tenant Space", filters=filters, fields=["property", "capacity"]):
		totals[room.property] = totals.get(room.property, 0) + max(cint(room.capacity), 1)
	return totals


def build(month=None, year=None, property=None) -> dict:
	"""Everything for the month, and how it compares with the month before."""
	month, year = (month, cint(year)) if month else last_month()
	start = getdate(f"{year}-{MONTHS.index(month) + 1:02d}-01")
	end = get_last_day(start)
	pl = profit.get_profit_and_loss(months=2, property=property, end=end)
	this, before = pl["months"][1], pl["months"][0]
	categories = profit.get_profit_and_loss(months=1, property=property, end=end)["categories"]

	# beds taken at the end of the month (or today, for this month)
	on = min(end, getdate(nowdate()))
	stays = staying_on(on, property)
	bed_totals = beds(property)
	taken = {}
	for stay in stays:
		taken[stay.property] = taken.get(stay.property, 0) + 1

	base = {"docstatus": 1}
	if property:
		base["property"] = property
	moved_in = frappe.get_all(
		ALLOTMENT,
		filters={**base, "allotment_date": ("between", (start, end))},
		fields=["tenant_name", "room", "property", "allotment_date"],
		order_by="allotment_date asc",
	)
	moved_out = frappe.get_all(
		ALLOTMENT,
		filters={**base, "vacate_date": ("between", (start, end)), "status": "Vacated"},
		fields=["tenant_name", "room", "property", "vacate_date"],
		order_by="vacate_date asc",
	)
	leaving = frappe.get_all(
		ALLOTMENT,
		filters={
			**base,
			"status": "Active",
			"expected_vacate_date": ("between", (getdate(nowdate()), add_days(nowdate(), 30))),
		},
		fields=["tenant_name", "room", "property", "expected_vacate_date"],
		order_by="expected_vacate_date asc",
	)

	unpaid = frappe.get_all(
		INVOICE,
		filters={**base, "outstanding_amount": (">", 0)},
		fields=["tenant", "tenant_name", "room", "outstanding_amount", "next_due_date", "due_date"],
	)
	owed = {}
	for invoice in unpaid:
		row = owed.setdefault(
			str(invoice.tenant),
			{"tenant": invoice.tenant, "tenant_name": invoice.tenant_name, "room": invoice.room, "amount": 0, "since": None},
		)  # fmt: skip
		row["amount"] += flt(invoice.outstanding_amount)
		due = (
			getdate(invoice.next_due_date or invoice.due_date)
			if (invoice.next_due_date or invoice.due_date)
			else None
		)
		if due and (not row["since"] or due < row["since"]):
			row["since"] = due
	today = getdate(nowdate())
	defaulters = sorted(
		(r for r in owed.values() if r["since"] and r["since"] < today), key=lambda r: -r["amount"]
	)

	enquiries = frappe.db.count(
		"Rent Lead",
		{**({"property": property} if property else {}), "creation": ("between", (start, f"{end} 23:59:59"))},
	)
	requests_opened = frappe.db.count(
		"Maintenance Request",
		{**({"property": property} if property else {}), "creation": ("between", (start, f"{end} 23:59:59"))},
	)
	requests_open = frappe.db.count(
		"Maintenance Request",
		{**({"property": property} if property else {}), "status": ("in", ("Open", "In Progress"))},
	)

	by_building = {
		p["property"]: p
		for p in profit.get_profit_and_loss(months=1, property=property, end=end)["properties"]
	}
	names = sorted(
		set(bed_totals) | set(by_building), key=lambda b: -(by_building.get(b, {}).get("collected") or 0)
	)
	buildings = [
		{
			"name": name,
			"collected": flt(by_building.get(name, {}).get("collected")),
			"invoiced": flt(by_building.get(name, {}).get("invoiced")),
			"expenses": flt(by_building.get(name, {}).get("expenses")),
			"profit": flt(by_building.get(name, {}).get("profit")),
			"beds": bed_totals.get(name, 0),
			"taken": taken.get(name, 0),
		}
		for name in names
		if frappe.db.get_value("Rent Property", name, "is_active")
	]

	total_beds = sum(bed_totals.values())
	return {
		"month": month,
		"year": year,
		"label": f"{month} {year}",
		"is_current": start == get_first_day(today),
		"collected": flt(this["collected"]),
		"invoiced": flt(this["invoiced"]),
		"expenses": flt(this["expenses"]),
		"profit": flt(this["profit"]),
		"collection_rate": round(flt(this["collected"]) / flt(this["invoiced"]) * 100)
		if flt(this["invoiced"])
		else None,
		"previous": {
			"label": f"{MONTHS[getdate(add_months(start, -1)).month - 1]}",
			"collected": flt(before["collected"]),
			"expenses": flt(before["expenses"]),
			"profit": flt(before["profit"]),
		},
		"top_expenses": categories[:5],
		"beds": total_beds,
		"taken": len(stays),
		"occupancy": round(len(stays) / total_beds * 100) if total_beds else 0,
		"moved_in": moved_in,
		"moved_out": moved_out,
		"leaving": leaving,
		"outstanding": sum(r["amount"] for r in owed.values()),
		"overdue": sum(r["amount"] for r in defaulters),
		"defaulters": [{**r, "since": str(r["since"])} for r in defaulters[:8]],
		"defaulter_count": len(defaulters),
		"enquiries": enquiries,
		"requests_opened": requests_opened,
		"requests_open": requests_open,
		"buildings": buildings,
		"business": business_name(property),
	}


def business_name(property=None) -> str:
	if property:
		return property
	buildings = frappe.get_all("Rent Property", filters={"is_active": 1}, pluck="name", limit=2)
	return buildings[0] if len(buildings) == 1 else _("your buildings")


def owner_name() -> str:
	settings = frappe.get_cached_doc(SETTINGS)
	return (settings.landlord_name or "").split(" ")[0] or _("there")


# ---------------------------------------------------------------- the message


def money(amount) -> str:
	"""Whole rupees with Indian grouping, as owners read them: ₹2,14,266."""
	currency = frappe.db.get_default("currency") or "INR"
	if currency != "INR":
		return notifications.money(round(flt(amount)))
	value = round(flt(amount))
	digits = str(abs(value))
	if len(digits) > 3:
		head, tail = digits[:-3], digits[-3:]
		groups = []
		while len(head) > 2:
			groups.insert(0, head[-2:])
			head = head[:-2]
		digits = ",".join(([head] if head else []) + groups) + "," + tail
	return f"{'-' if value < 0 else ''}₹{digits}"


def text(s: dict) -> str:
	"""For WhatsApp (shared by hand, so it can have lines and emphasis)."""
	trend = ""
	if s["previous"]["collected"]:
		change = round((s["collected"] - s["previous"]["collected"]) / s["previous"]["collected"] * 100)
		trend = f" ({'+' if change >= 0 else ''}{change}% vs {s['previous']['label']})"
	lines = [
		f"*{s['label']} at {s['business']}*",
		"",
		f"Collected: {money(s['collected'])} of {money(s['invoiced'])} invoiced"
		+ (f" ({s['collection_rate']}%)" if s["collection_rate"] is not None else "")
		+ trend,
		f"Spent: {money(s['expenses'])}"
		+ (
			" (" + ", ".join(f"{c['category']} {money(c['amount'])}" for c in s["top_expenses"][:3]) + ")"
			if s["top_expenses"]
			else ""
		),
		f"*Profit: {money(s['profit'])}*",
		"",
		f"Beds: {s['taken']} of {s['beds']} taken ({s['occupancy']}%)",
		f"Moved in: {len(s['moved_in'])} · moved out: {len(s['moved_out'])}"
		+ (f" · leaving in 30 days: {len(s['leaving'])}" if s["leaving"] else ""),
	]
	if s["outstanding"]:
		lines += ["", f"Still to collect: {money(s['outstanding'])}"]
		for d in s["defaulters"][:5]:
			lines.append(f"- {d['tenant_name']} (room {d['room']}): {money(d['amount'])}")
		if s["defaulter_count"] > 5:
			lines.append(f"- and {s['defaulter_count'] - 5} more")
	if len(s["buildings"]) > 1:
		lines += [""] + [
			f"{b['name']}: {money(b['collected'])} in, {money(b['profit'])} profit, {b['taken']}/{b['beds']} beds"
			for b in s["buildings"]
		]
	if s["enquiries"] or s["requests_open"]:
		lines += ["", f"New enquiries: {s['enquiries']} · open requests: {s['requests_open']}"]
	return "\n".join(lines)


def template_params(s: dict) -> list[str]:
	return [
		owner_name(),
		s["label"],
		s["business"],
		money(s["collected"]),
		money(s["invoiced"]),
		money(s["expenses"]),
		money(s["profit"]),
		str(s["taken"]),
		str(s["beds"]),
		money(s["outstanding"]),
		_("Full report: {0}").format(report_url(s)),
	]


def report_url(s: dict) -> str:
	return get_url(f"/rent/summary?month={s['month']}&year={s['year']}")


def html(s: dict) -> str:
	"""For email."""
	esc = frappe.utils.escape_html
	rows = "".join(
		f"<tr><td style='padding:4px 12px 4px 0'>{esc(label)}</td><td style='text-align:right'><b>{value}</b></td></tr>"
		for label, value in (
			(_("Collected"), money(s["collected"])),
			(_("Invoiced"), money(s["invoiced"])),
			(_("Spent"), money(s["expenses"])),
			(_("Profit"), money(s["profit"])),
			(_("Beds taken"), f"{s['taken']} of {s['beds']} ({s['occupancy']}%)"),
			(_("Still to collect"), money(s["outstanding"])),
		)
	)
	owing = "".join(
		f"<li>{esc(d['tenant_name'])} (room {esc(str(d['room']))}): {money(d['amount'])}</li>"
		for d in s["defaulters"]
	)
	buildings = "".join(
		f"<tr><td style='padding:4px 12px 4px 0'>{esc(b['name'])}</td><td>{money(b['collected'])}</td>"
		f"<td>{money(b['expenses'])}</td><td><b>{money(b['profit'])}</b></td><td>{b['taken']}/{b['beds']}</td></tr>"
		for b in s["buildings"]
	)
	return f"""
<p>{_("Hello {0},").format(esc(owner_name()))}</p>
<p>{_("Here is how {0} went at {1}.").format(esc(s["label"]), esc(s["business"]))}</p>
<table>{rows}</table>
{f"<h4>{_('Who still owes')}</h4><ul>{owing}</ul>" if owing else ""}
{f"<h4>{_('By building')}</h4><table><tr><th align='left'>{_('Building')}</th><th>{_('In')}</th><th>{_('Spent')}</th><th>{_('Profit')}</th><th>{_('Beds')}</th></tr>{buildings}</table>" if len(s["buildings"]) > 1 else ""}
<p>{_("Moved in: {0}. Moved out: {1}. New enquiries: {2}.").format(len(s["moved_in"]), len(s["moved_out"]), s["enquiries"])}</p>
<p><a href="{report_url(s)}">{_("See the full report")}</a></p>
"""


# ---------------------------------------------------------------- sending


def owner_contact() -> frappe._dict:
	settings = frappe.get_cached_doc(SETTINGS)
	return frappe._dict(
		name=None,
		mobile_no=settings.owner_summary_phone or settings.landlord_phone,
		email_id=settings.owner_summary_email,
	)


def send(month=None, year=None) -> list[str]:
	s = build(month, year)
	owner = owner_contact()
	if not (owner.mobile_no or owner.email_id):
		frappe.throw(_("Add the owner's WhatsApp number or email in Settings first."))
	return notifications.send(
		"Owner Summary",
		owner,
		text(s),
		template_params(s),
		subject=_("{0}: {1} collected, {2} profit").format(
			s["label"], money(s["collected"]), money(s["profit"])
		),
		html=html(s),
	)


def send_monthly():
	"""Daily: on the chosen day, send the owner last month's summary (once)."""
	settings = frappe.get_cached_doc(SETTINGS)
	if not cint(settings.owner_summary_enabled):
		return
	today = getdate(nowdate())
	if today.day != min(max(cint(settings.owner_summary_day) or 1, 1), 28):
		return
	if frappe.db.exists(
		notifications.LOG,
		{"message_type": "Owner Summary", "status": "Sent", "creation": (">=", get_first_day(today))},
	):
		return
	try:
		send()
	except frappe.ValidationError:
		frappe.clear_last_message()  # no contact set up: nothing to send
