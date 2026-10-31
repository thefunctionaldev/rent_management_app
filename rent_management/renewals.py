# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Agreement renewals: nobody's agreement runs out unnoticed.

Managers (and wardens with rooms and tenants) hear 30 days and 7 days before an agreement
ends, and every Monday which ones end in the next 30 days; the tenant sees it in their app.
Renewing a stay starts a new term the day after the old one ends (or today, if it ended
long ago) for the usual number of months, optionally at a new rent from that day, and sends
the renewed agreement to the tenant to sign in the same way as at check-in (checkin.py),
straight to the signing step since their details are on file.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, getdate, now_datetime, nowdate

ALLOTMENT = "Tenant Space Allotment"
CHECKIN = "Tenant Check-in"
REMIND_DAYS = (30, 7)
LATE_DAYS = 60  # renewing an agreement that ended longer ago than this starts it today


def default_months(stay) -> int:
	return (
		cint(stay.agreement_months)
		or cint(frappe.db.get_single_value("Rent Management Settings", "default_agreement_months"))
		or 11
	)


def next_term(stay, months=None) -> dict:
	"""The dates a renewal would have."""
	months = cint(months) or default_months(stay)
	today = getdate(nowdate())
	end = getdate(stay.agreement_end_date) if stay.agreement_end_date else None
	start = add_days(end, 1) if end and date_diff(today, end) <= LATE_DAYS else today
	return {
		"months": months,
		"start": start,
		"end": add_days(add_months(start, months), -1),
		"rent": flt(stay.rent_amount),
		"increase_percent": flt(stay.rent_increase_percent),
	}


def preview(allotment, months=None) -> dict:
	stay = frappe.get_doc(ALLOTMENT, allotment)
	return {
		**next_term(stay, months),
		"current_start": stay.agreement_start_date or stay.allotment_date,
		"current_end": stay.agreement_end_date,
		"renewals": cint(stay.renewals),
		"suggested_rent": round(flt(stay.rent_amount) * (1 + flt(stay.rent_increase_percent) / 100))
		if flt(stay.rent_increase_percent)
		else flt(stay.rent_amount),
	}


def renew(allotment, months=None, new_rent=None, send_for_signing=1) -> dict:
	from rent_management import activity

	stay = frappe.get_doc(ALLOTMENT, allotment)
	stay.check_permission("write")
	if stay.docstatus != 1 or stay.status != "Active":
		frappe.throw(_("Only an active stay can be renewed."))
	if stay.expected_vacate_date:
		frappe.throw(_("{0} has given notice. Withdraw the notice first to renew.").format(stay.tenant_name))
	term = next_term(stay, months)
	if term["months"] < 1 or term["months"] > 60:
		frappe.throw(_("Renew for 1 to 60 months."))
	stay.db_set(
		{
			"agreement_start_date": term["start"],
			"agreement_end_date": term["end"],
			"agreement_months": term["months"],
			"renewals": cint(stay.renewals) + 1,
			"renewed_on": now_datetime(),
		}
	)
	if new_rent and flt(new_rent) != flt(stay.rent_amount):
		stay.reload()
		stay.revise_rent(flt(new_rent), term["start"], _("Agreement renewed"))
	activity.log(
		"Stays",
		_("renewed the agreement of {0} until {1}").format(
			stay.tenant_name, frappe.utils.formatdate(term["end"])
		),
		stay,
	)
	result = {**term, "rent": flt(frappe.db.get_value(ALLOTMENT, allotment, "rent_amount"))}
	if cint(send_for_signing):
		result["signing"] = send_for_signing_now(stay.name)
	return result


def send_for_signing_now(allotment, purpose="Renewal") -> dict:
	"""A link for the tenant to sign the renewed (or, after a room change, updated) agreement:
	straight to signing."""
	from rent_management.checkin import checkin_url

	stay = frappe.get_doc(ALLOTMENT, allotment)
	for name in frappe.get_all(CHECKIN, filters={"allotment": allotment, "status": ("in", ("Sent", "Details Submitted"))}, pluck="name"):  # fmt: skip
		frappe.db.set_value(CHECKIN, name, "status", "Cancelled")  # an older link would sign the old terms
	doc = frappe.get_doc(
		{
			"doctype": CHECKIN,
			"tenant": stay.tenant,
			"allotment": stay.name,
			"purpose": purpose,
			"status": "Details Submitted",  # their details are on file: just read and sign
			"sent_on": now_datetime(),
			"details_submitted_on": now_datetime(),
		}
	).insert(ignore_permissions=True)
	link = checkin_url(doc)
	if purpose == "Room Change":
		subject = _("Sign your agreement for your new room")
		message = _("Your agreement is updated for room {0}. Read and sign it here: {1}").format(
			stay.room, link
		)
	else:
		subject = _("Sign your renewed agreement")
		message = _("Your agreement is renewed until {0}. Read and sign it here: {1}").format(
			frappe.utils.formatdate(stay.agreement_end_date), link
		)
	tell_tenant(stay, subject, message, link)
	tenant = frappe.db.get_value("Tenant", stay.tenant, ["mobile_no"], as_dict=True)
	return {"name": doc.name, "url": link, "mobile_no": tenant.mobile_no}


def tell_tenant(stay, subject, message, link=None):
	from rent_management.notifications import email_configured

	t = frappe.db.get_value("Tenant", stay.tenant, ["user", "email_id"], as_dict=True) or frappe._dict()
	if t.user:
		frappe.get_doc(
			{"doctype": "Notification Log", "for_user": t.user, "type": "Alert", "subject": subject,
				"email_content": message, "link": link or "/tenant/profile"}
		).insert(ignore_permissions=True)  # fmt: skip
	elif t.email_id and email_configured():
		frappe.sendmail(recipients=[t.email_id], subject=subject, message=f"<p>{message}</p>")


def signed_after_renewal(stay) -> dict | None:
	"""The signature of the current terms: after the latest renewal, if renewed."""
	filters = {"allotment": stay.name, "status": "Signed"}
	if stay.get("renewed_on"):
		filters["signed_on"] = (">=", stay.renewed_on)
	return frappe.db.get_value(
		CHECKIN,
		filters,
		["name", "signed_on", "signed_name", "otp_channel", "otp_sent_to"],
		as_dict=True,
		order_by="signed_on desc",
	)


# ---------------------------------------------------------------- reminding


def ending(within_days=30, property=None) -> list:
	today = getdate(nowdate())
	filters = {
		"docstatus": 1,
		"status": "Active",
		"expected_vacate_date": ("is", "not set"),
		"agreement_end_date": ("between", (add_days(today, -LATE_DAYS), add_days(today, within_days))),
	}
	if property:
		filters["property"] = property
	return frappe.get_all(
		ALLOTMENT,
		filters=filters,
		fields=["name", "tenant", "tenant_name", "room", "property", "agreement_end_date"],
		order_by="agreement_end_date asc",
	)


def remind():
	"""Daily: 30 and 7 days before an agreement ends, managers and the tenant hear; on Mondays,
	managers get the list of those ending in the next 30 days (or already ended)."""
	from rent_management.portal import notify_managers

	today = getdate(nowdate())
	rows = ending()
	for row in rows:
		days = date_diff(row.agreement_end_date, today)
		if days not in REMIND_DAYS:
			continue
		when = frappe.utils.formatdate(row.agreement_end_date)
		notify_managers(
			_("{0}'s agreement ends in {1} days").format(row.tenant_name, days),
			_("Room {0}. It ends on {1}: renew it from their page, or plan for the room.").format(
				row.room, when
			),
			link=f"/rent/tenants/{row.tenant}",
			area="rooms",
			property=row.property,
		)
		if days == REMIND_DAYS[0]:
			tell_tenant(
				frappe._dict(tenant=row.tenant),
				_("Your agreement ends on {0}").format(when),
				_("Your rental agreement ends on {0}. Talk to your landlord about renewing it.").format(when),
			)
	if today.weekday() == 0 and rows:
		notify_managers(
			_("{0} agreements end soon").format(len(rows)),
			", ".join(
				f"{r.tenant_name} ({frappe.utils.formatdate(r.agreement_end_date)})" for r in rows[:10]
			),
			link="/rent/",
			area="rooms",
		)
