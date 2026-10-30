# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The notice board: announcements from the manager to the tenants of a building (or all).

A published notice shows in the tenant app (Notices, with an unread badge and the newest on
Home), wakes the tenants' phones that have notifications on (see pwa.py), and if asked is
also sent on WhatsApp and by email. Managers see how many tenants have seen it.

	rent_notice  Hello {{1}}, a notice from {{2}}: {{3}}. {{4}}
"""

import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_url, getdate, now_datetime, nowdate

NOTICE = "Rent Notice"
READ = "Rent Notice Read"
ALLOTMENT = "Tenant Space Allotment"
FIELDS = ("title", "message", "category", "property", "pinned", "expires_on", "send_whatsapp")


def stays_for(property=None) -> list:
	"""The current stays a notice for the building (or all buildings) reaches."""
	filters = {"docstatus": 1, "status": "Active"}
	if property:
		filters["property"] = property
	return frappe.get_all(ALLOTMENT, filters=filters, fields=["tenant", "property", "allotment_date"])


def tenants_for(property=None) -> list[str]:
	return sorted({str(s.tenant) for s in stays_for(property)})


# ---------------------------------------------------------------- managers


def save(data) -> str:
	data = frappe.parse_json(data)
	doc = frappe.get_doc(NOTICE, data["name"]) if data.get("name") else frappe.new_doc(NOTICE)
	doc.update({field: data.get(field) for field in FIELDS if field in data})
	doc.title = (doc.title or "").strip()
	doc.message = (doc.message or "").strip()
	doc.property = doc.property or None
	doc.expires_on = doc.expires_on or None
	if doc.expires_on and getdate(doc.expires_on) < getdate(nowdate()):
		frappe.throw(_("Choose a date from today on, or leave it empty."))
	doc.save()
	return doc.name


def publish(name):
	doc = frappe.get_doc(NOTICE, name)
	if doc.status == "Published":
		frappe.throw(_("This notice is already published."))
	tenants = tenants_for(doc.property)
	if not tenants:
		frappe.throw(_("Nobody is staying there right now."))
	doc.update(
		{
			"status": "Published",
			"published_on": now_datetime(),
			"published_by": frappe.session.user,
			"recipients": len(tenants),
			"seen": 0,
		}
	)
	doc.save()
	frappe.enqueue(
		"rent_management.notices.deliver",
		name=doc.name,
		queue="long",
		timeout=1800,
		enqueue_after_commit=True,
	)


def delete(name):
	frappe.db.delete(READ, {"notice": name})
	frappe.delete_doc(NOTICE, name)


def withdraw(name):
	"""Take it off the notice board (it can be published again)."""
	doc = frappe.get_doc(NOTICE, name)
	doc.status = "Draft"
	doc.save()


def deliver(name):
	"""Background: wake the tenants' phones and, if asked, send it on WhatsApp and by email."""
	from rent_management import notifications, pwa

	doc = frappe.get_doc(NOTICE, name)
	tenants = frappe.get_all(
		"Tenant",
		filters={"name": ("in", tenants_for(doc.property) or [""])},
		fields=["name", "first_name", "full_name", "mobile_no", "email_id", "user"],
	)
	users = {t.user for t in tenants if t.user}
	for user in frappe.get_all(
		pwa.SUBSCRIPTION, filters={"user": ("in", list(users) or [""])}, pluck="user", distinct=True
	):
		pwa.send_push(user)
	if not cint(doc.send_whatsapp):
		return
	sent = 0
	place = building_name(doc.property)
	for tenant in tenants:
		params = [
			tenant.first_name or tenant.full_name,
			place,
			doc.title,
			one_line(doc.message)[:700]
			+ " "
			+ _("See it in the app: {0}").format(get_url("/tenant/notices")),
		]
		text = _("Hello {0}, a notice from {1}: {2}. {3}").format(*params)
		statuses = notifications.send("Notice", tenant, text, params, subject=f"{place}: {doc.title}")
		sent += "Sent" in statuses
	frappe.db.set_value(NOTICE, name, "messages_sent", sent)


def one_line(text) -> str:
	"""WhatsApp template values can't have new lines."""
	return re.sub(r"\s*\n+\s*", " · ", (text or "").strip())


def building_name(property=None) -> str:
	if property:
		return frappe.db.get_value("Rent Property", property, "property_name") or property
	from rent_management.pwa import business_name

	return business_name() or _("your PG")


def get_notices(property=None) -> dict:
	rows = frappe.get_all(
		NOTICE,
		or_filters=[["property", "is", "not set"], ["property", "=", property]] if property else None,
		fields=["name", *FIELDS, "status", "published_on", "recipients", "seen", "messages_sent", "creation"],
		order_by="creation desc",
		limit=200,
	)
	# published first, pinned first, newest first
	rows.sort(
		key=lambda r: (r.status != "Published", not r.pinned, -(r.published_on or r.creation).timestamp())
	)
	today = getdate(nowdate())
	for row in rows:
		row.expired = bool(row.expires_on and getdate(row.expires_on) < today)
	return {"notices": rows, "tenants": len(tenants_for(property))}


# ---------------------------------------------------------------- tenants


def visible_filters(stay) -> dict:
	return {
		"status": "Published",
		"published_on": (">=", add_days(stay.allotment_date, -60)),  # what was up when they moved in
	}


def current(stay) -> list:
	rows = frappe.get_all(
		NOTICE,
		filters=visible_filters(stay),
		or_filters=[["property", "is", "not set"], ["property", "=", stay.property]],
		fields=["name", "title", "message", "category", "pinned", "expires_on", "published_on", "property"],
		order_by="pinned desc, published_on desc",
		limit=50,
	)
	today = getdate(nowdate())
	return [r for r in rows if not r.expires_on or getdate(r.expires_on) >= today]


def for_tenant(tenant, stay) -> list:
	rows = current(stay)
	read = set(
		frappe.get_all(
			READ, filters={"tenant": tenant, "notice": ("in", [r.name for r in rows] or [""])}, pluck="notice"
		)
	)
	for row in rows:
		row.unread = row.name not in read
	return rows


def unread(tenant, stay) -> list:
	return [r for r in for_tenant(tenant, stay) if r.unread]


def mark_read(tenant, names):
	for name in frappe.parse_json(names) if isinstance(names, str) else names:
		if frappe.db.exists(READ, {"notice": name, "tenant": tenant}) or not frappe.db.exists(NOTICE, name):
			continue
		frappe.get_doc({"doctype": READ, "notice": name, "tenant": tenant, "read_on": now_datetime()}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value(
			NOTICE, name, "seen", frappe.db.count(READ, {"notice": name}), update_modified=False
		)


def pending_for_user(user) -> list[dict]:
	"""For a tenant's phone after a push (pwa.pending): notices published in the last hour, unread."""
	from rent_management.portal import current_stay

	tenant = frappe.db.get_value("Tenant", {"user": user})
	stay = current_stay(tenant) if tenant else None
	if not stay:
		return []
	since = now_datetime().timestamp() - 3600
	return [
		{"id": r.name, "title": r.title, "body": one_line(r.message)[:240], "url": "/tenant/notices"}
		for r in unread(tenant, stay)
		if r.published_on and r.published_on.timestamp() >= since
	][:3]
