# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The public listing page (/stay) and the leads it brings in.

Visitors see each building's photos, room types, prices and free beds, and send an
enquiry, ask for a visit, or hold a bed by paying a token. The token is paid straight to
the landlord: with their Razorpay account (a payment link), or by UPI, which the
landlord confirms. Managers follow every lead in the Leads page until it moves in, which
makes the tenant and their stay, and counts the token towards the first rent invoice.
"""

from collections import defaultdict
from urllib.parse import quote, urlencode

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import (
	add_days,
	add_months,
	cint,
	flt,
	get_datetime,
	get_first_day,
	get_url,
	getdate,
	now_datetime,
	nowdate,
	validate_email_address,
)

from rent_management import razorpay, referrals, rent_collection, subscription
from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

LEAD = "Rent Lead"
SETTINGS = "Rent Management Settings"
OPEN_STATES = ("New", "Contacted", "Visit Scheduled", "Visited", "Booked")
TOKEN_MODES = {"UPI": "UPI", "Cash": "Cash", "Bank Transfer": "Bank Transfer"}  # else "Other"


def listing_enabled() -> bool:
	return (
		bool(cint(frappe.db.get_single_value(SETTINGS, "listing_enabled")))
		and not subscription.skip_if_lapsed()
	)


def only_when_listed():
	if not listing_enabled():
		raise frappe.PageDoesNotExistError


def token_amount() -> float:
	return flt(frappe.db.get_single_value(SETTINGS, "booking_token_amount"))


def listing_url(building=None) -> str:
	slug = frappe.db.get_value("Rent Property", building, "listing_slug") if building else None
	return get_url(f"/stay/{slug}" if slug else "/stay")


# ---------------------------------------------------------------- what the page shows


def get_room_types(building: str) -> list[dict]:
	"""Room types of a building with their lowest rent and free beds, less beds held by bookings."""
	rooms = frappe.get_all(
		"Tenant Space",
		filters={"property": building, "status": ("!=", "Under Renovation")},
		fields=["name", "room_type", "capacity", "occupied_beds", "room_rent"],
	)
	held = defaultdict(int)
	for lead in frappe.get_all(
		LEAD, filters={"property": building, "status": "Booked"}, fields=["room", "room_type"]
	):
		room_type = (
			frappe.db.get_value("Tenant Space", lead.room, "room_type") if lead.room else lead.room_type
		)
		held[room_type] += 1

	types = {}
	for room in rooms:
		if not room.room_type:
			continue
		row = types.setdefault(room.room_type, {"type": room.room_type, "rent": None, "beds": 0, "free": 0})
		rent = flt(room.room_rent)
		row["rent"] = rent if row["rent"] is None else min(row["rent"], rent)
		row["beds"] += max(cint(room.capacity), 1)
		row["free"] += max(max(cint(room.capacity), 1) - cint(room.occupied_beds), 0)

	result = []
	for name, row in types.items():
		room_type = frappe.get_cached_doc("Tenant Space Type", name)
		row["free"] = max(row["free"] - held[name], 0)
		row.update(
			{
				"description": room_type.description,
				"deposit": flt(room_type.security_deposit) if room_type.deposit_applicable else 0,
				"furnished": cint(room_type.is_furnished),
				"attached_bathroom": cint(room_type.has_attached_bathroom),
			}
		)
		result.append(row)
	return sorted(result, key=lambda r: flt(r["rent"]))


def building_card(doc) -> dict:
	room_types = get_room_types(doc.name)
	return {
		"slug": doc.listing_slug,
		"name": doc.property_name,
		"address": doc.address,
		"city": doc.city,
		"state": doc.state,
		"pincode": doc.pincode,
		"image": doc.image,
		"description": doc.description,
		"amenities": [a.strip() for a in (doc.amenities or "").replace(",", "\n").splitlines() if a.strip()],
		"listing_for": doc.listing_for,
		"food_included": cint(doc.food_included),
		"map_link": doc.map_link,
		"room_types": room_types,
		"free_beds": sum(r["free"] for r in room_types),
		"rent_from": min((r["rent"] for r in room_types if r["rent"]), default=None),
	}


def listed_buildings():
	return frappe.get_all(
		"Rent Property",
		filters={"is_active": 1, "show_on_listing": 1},
		pluck="name",
		order_by="creation asc",
	)


def get_building(slug):
	name = frappe.db.get_value("Rent Property", {"listing_slug": slug, "is_active": 1, "show_on_listing": 1})
	if not name:
		raise frappe.DoesNotExistError(_("This building isn't listed."))
	return frappe.get_doc("Rent Property", name)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=600, seconds=60 * 60)
def get_listing(building=None, ref=None):
	only_when_listed()
	settings = frappe.get_single(SETTINGS)
	options = rent_collection.get_payment_options()
	cards = (
		[building_card(get_building(building))]
		if building
		else [building_card(frappe.get_doc("Rent Property", b)) for b in listed_buildings()]
	)
	return {
		"buildings": cards,
		"buildings_count": len(listed_buildings()),
		"brand": settings.upi_payee_name or settings.landlord_name or (cards[0]["name"] if cards else ""),
		"phone": settings.landlord_phone,
		"token": token_amount() if (options["razorpay"] or options["upi"]) else 0,
		"currency_symbol": frappe.db.get_value("Currency", "INR", "symbol") or "₹",
		"today": nowdate(),
		"referred_by": referrals.referrer_on_listing(ref),
	}


# ---------------------------------------------------------------- enquiries and bookings


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def enquire(
	building,
	name,
	mobile_no,
	email_id=None,
	room_type=None,
	move_in_date=None,
	visit_on=None,
	message=None,
	gender=None,
	book=0,
	website=None,
	ref=None,
):
	"""An enquiry from the listing page. `website` is a honeypot: people leave it empty."""
	only_when_listed()
	if website:
		return {"key": frappe.generate_hash(length=32), "booking": False}  # pretend all is well
	doc = get_building(building)
	room_types = {r["type"]: r for r in get_room_types(doc.name)}
	if room_type and room_type not in room_types:
		frappe.throw(_("Please choose one of the room types of {0}.").format(doc.property_name))
	email_id = (email_id or "").strip().lower() or None
	if email_id and not validate_email_address(email_id):
		frappe.throw(_("Please enter a valid email address."))
	if move_in_date and getdate(move_in_date) < getdate(nowdate()):
		frappe.throw(_("The move-in date can't be in the past."))
	if visit_on:
		visit_on = get_datetime(visit_on)
		if visit_on < now_datetime() or visit_on > get_datetime(add_days(nowdate(), 60)):
			frappe.throw(_("Please choose a visit time in the next 60 days."))

	booking = bool(cint(book)) and token_amount() > 0 and bool(room_type)
	if booking and not room_types[room_type]["free"]:
		frappe.throw(_("{0} is full right now. Send an enquiry and we'll call you.").format(room_type))
	options = rent_collection.get_payment_options()
	booking = booking and (options["razorpay"] or options["upi"])

	lead = frappe.get_doc(
		{
			"doctype": LEAD,
			"lead_name": (name or "").strip()[:140],
			"mobile_no": (mobile_no or "")[:20],
			"email_id": email_id,
			"gender": gender if gender in ("Male", "Female", "Other") else None,
			"property": doc.name,
			"room_type": room_type,
			"move_in_date": move_in_date or None,
			"visit_on": visit_on or None,
			"message": (message or "").strip()[:1000] or None,
			"status": "Visit Scheduled" if visit_on else "New",
			"source": "Listing",
			"token_amount": token_amount() if booking else None,
			"token_status": "Pending" if booking else None,
			"ip_address": frappe.local.request_ip,
		}
	)
	if not lead.lead_name:
		frappe.throw(_("Please enter your name."))
	referrals.on_enquiry(lead, ref)  # came through a tenant's link
	lead.flags.ignore_permissions = True
	lead.insert()

	what = _("wants to book") if booking else (_("wants to visit") if visit_on else _("enquired about"))
	notify_managers(
		lead,
		_("New lead: {0} {1} {2}").format(lead.lead_name, what, doc.property_name),
		_("{0} ({1}) {2} {3}{4}.").format(
			lead.lead_name,
			lead.mobile_no,
			what,
			room_type or doc.property_name,
			_(" on {0}").format(frappe.utils.format_datetime(visit_on, "d MMM, h:mm a")) if visit_on else "",
		),
	)
	return {"key": lead.access_key, "booking": booking}


def lead_by_key(key):
	name = frappe.db.get_value(LEAD, {"access_key": key or "-"})
	if not name:
		raise frappe.DoesNotExistError(_("This booking link isn't valid."))
	return frappe.get_doc(LEAD, name)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=300, seconds=60 * 60)
def get_booking(key):
	"""What the visitor sees after enquiring or paying: never more than their own lead."""
	lead = lead_by_key(key)
	if lead.token_status == "Pending" and lead.payment_link_id:
		sync_token_link(lead)
		lead.reload()
	upi = upi_link(lead) if lead.token_status == "Pending" else None
	return {
		"name": lead.lead_name.split(" ")[0],
		"building": frappe.db.get_value("Rent Property", lead.property, "property_name"),
		"slug": frappe.db.get_value("Rent Property", lead.property, "listing_slug"),
		"room_type": lead.room_type,
		"status": lead.status,
		"visit_on": lead.visit_on,
		"token_amount": flt(lead.token_amount),
		"token_status": lead.token_status or None,
		"online": bool(rent_collection.get_auth()) and lead.token_status == "Pending",
		"upi_link": upi,
		"upi_qr": rent_collection.qr_data_uri(upi) if upi else None,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def pay_token(key):
	"""A payment link for the token, on the landlord's Razorpay account."""
	lead = lead_by_key(key)
	if lead.token_status != "Pending":
		frappe.throw(_("This token is already paid."))
	return token_link(lead)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def report_token(key, reference=None):
	"""The visitor paid the token by UPI; the landlord checks it and confirms."""
	lead = lead_by_key(key)
	if lead.token_status != "Pending":
		return get_booking(key)
	lead.db_set(
		{
			"token_status": "Reported",
			"token_mode": "UPI",
			"token_reference": (reference or "").strip()[:140] or None,
		}
	)
	notify_managers(
		lead,
		_("Token reported by {0}").format(lead.lead_name),
		_(
			"{0} says they paid the {1} token by UPI (reference {2}). Check your UPI app and confirm it."
		).format(
			lead.lead_name,
			frappe.utils.fmt_money(lead.token_amount, currency="INR"),
			lead.token_reference or "-",
		),
	)
	return get_booking(key)


def upi_link(lead) -> str | None:
	settings = frappe.get_single(SETTINGS)
	if not settings.upi_id or flt(lead.token_amount) <= 0:
		return None
	params = {
		"pa": settings.upi_id.strip(),
		"pn": settings.upi_payee_name or lead.property,
		"am": f"{flt(lead.token_amount):.2f}",
		"cu": "INR",
		"tn": f"Booking {lead.name}"[:50],
	}
	return "upi://pay?" + urlencode(params, quote_via=quote)


def token_link(lead) -> str:
	auth = rent_collection.get_auth()
	if not auth:
		frappe.throw(_("Online payment isn't set up. Please pay by UPI."))
	if lead.payment_link_id and lead.payment_link_url:
		return lead.payment_link_url
	customer = {"name": lead.lead_name, "contact": lead.mobile_no}
	if lead.email_id:
		customer["email"] = lead.email_id
	slug = frappe.db.get_value("Rent Property", lead.property, "listing_slug")
	link = razorpay.create_payment_link(
		{
			"amount": razorpay.to_subunits(lead.token_amount),
			"currency": "INR",
			"accept_partial": False,
			"description": _("Token to hold a bed at {0}").format(lead.property)[:2048],
			"reference_id": f"{lead.name}-{frappe.generate_hash(length=5)}",
			"customer": customer,
			"notify": {"sms": False, "email": False},
			"reminder_enable": False,
			"notes": {"site": frappe.local.site, "lead": lead.name},
			"callback_url": get_url(f"/stay/{slug}?booking={lead.access_key}"),
			"callback_method": "get",
		},
		auth,
	)
	lead.db_set({"payment_link_id": link["id"], "payment_link_url": link["short_url"]})
	return link["short_url"]


def sync_token_link(lead) -> bool:
	auth = rent_collection.get_auth()
	if not (auth and lead.payment_link_id):
		return False
	link = razorpay.get_payment_link(lead.payment_link_id, auth)
	for payment in link.get("payments") or []:
		if payment.get("status") == "captured":
			return record_token_payment(lead, payment["payment_id"], flt(payment.get("amount")) / 100)
	return False


def record_token_payment(lead, payment_id, amount) -> bool:
	"""The token arrived on Razorpay: the bed is held. Idempotent."""
	lead = frappe.get_doc(LEAD, lead.name, for_update=True)
	if lead.token_status == "Paid":
		return False
	lead.update(
		{
			"token_status": "Paid",
			"token_amount": flt(amount, 2),
			"token_paid_on": nowdate(),
			"token_mode": "Razorpay",
			"token_reference": payment_id,
			"status": "Booked" if lead.status in OPEN_STATES else lead.status,
		}
	)
	lead.flags.ignore_permissions = True
	frappe.flags.recording_online_payment = True  # the money is in, even if the plan lapsed
	try:
		lead.save()
	finally:
		frappe.flags.recording_online_payment = False
	notify_managers(
		lead,
		_("Bed booked: {0} paid the token").format(lead.lead_name),
		_("{0} ({1}) paid {2} online to hold a bed at {3}.").format(
			lead.lead_name, lead.mobile_no, frappe.utils.fmt_money(amount, currency="INR"), lead.property
		),
	)
	return True


def reconcile_token_links():
	"""Scheduler (daily): pick up token payments the webhook and the return page missed."""
	if not rent_collection.get_auth():
		return
	for name in frappe.get_all(
		LEAD, filters={"token_status": "Pending", "payment_link_id": ("is", "set")}, pluck="name"
	):
		frappe.db.savepoint("token_link")
		try:
			sync_token_link(frappe.get_doc(LEAD, name))
		except Exception:
			frappe.db.rollback(save_point="token_link")
			frappe.log_error(title=f"Could not check the token payment of {name}")


def notify_managers(lead, subject, message):
	from rent_management.portal import notify_managers as notify

	notify(
		subject,
		message + " " + _("Open it in Leads: {0}").format(get_url(f"/rent/leads?lead={lead.name}")),
		link=f"/rent/leads?lead={lead.name}",
		area="leads",
		property=lead.property,
	)


# ---------------------------------------------------------------- managers

LEAD_FIELDS = (
	"lead_name",
	"mobile_no",
	"email_id",
	"gender",
	"occupation",
	"status",
	"source",
	"referred_by",
	"visit_on",
	"lost_reason",
	"property",
	"room_type",
	"move_in_date",
	"message",
	"notes",
	"room",
	"token_amount",
)
LIST_FIELDS = [
	"name",
	*LEAD_FIELDS,
	"referred_by_name",
	"token_status",
	"token_paid_on",
	"token_mode",
	"token_reference",
	"payment_link_url",
	"tenant",
	"allotment",
	"creation",
]


def get_leads(status=None, property=None) -> dict:
	base = {"property": property} if property else {}
	counts = defaultdict(int)
	for row in frappe.get_all(LEAD, filters=base, pluck="status"):
		counts[row] += 1
	filters = dict(base)
	if status == "open":
		filters["status"] = ("in", OPEN_STATES)
	elif status:
		filters["status"] = status
	leads = frappe.get_all(LEAD, filters=filters, fields=LIST_FIELDS, order_by="creation desc", limit=500)
	order = {s: i for i, s in enumerate(("Booked", "Visit Scheduled", "New", "Contacted", "Visited"))}
	leads.sort(key=lambda lead: order.get(lead.status, 9))
	return {
		"leads": leads,
		"counts": dict(counts),
		"open": sum(counts[s] for s in OPEN_STATES),
		"listing_enabled": listing_enabled(),
		"listing_url": listing_url(property),
	}


def save_lead(data) -> str:
	from rent_management.api import pick

	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc(LEAD, data["name"])
		doc.update(pick(data, LEAD_FIELDS))
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": LEAD, "source": "Walk-in", **pick(data, LEAD_FIELDS)}).insert()
	return doc.name


def record_token(name, amount, mode="Cash", reference=None, paid_on=None):
	"""A token paid in cash or by UPI, or a reported UPI payment the manager has checked."""
	doc = frappe.get_doc(LEAD, name)
	if flt(amount) <= 0:
		frappe.throw(_("Enter the token amount."))
	doc.update(
		{
			"token_amount": flt(amount),
			"token_status": "Paid",
			"token_mode": mode,
			"token_reference": reference or doc.token_reference,
			"token_paid_on": paid_on or nowdate(),
			"status": "Booked" if doc.status in OPEN_STATES else doc.status,
		}
	)
	doc.save()


def move_in(
	name,
	room,
	allotment_date=None,
	bed_no=None,
	rent_amount=None,
	security_deposit=None,
	deposit_collected=0,
) -> dict:
	"""The lead moves in: their tenant profile and stay are made, and a paid token is
	recorded as a payment on their first rent invoice."""
	from rent_management import api

	lead = frappe.get_doc(LEAD, name)
	if lead.status == "Moved In":
		frappe.throw(_("{0} has already moved in.").format(lead.lead_name))
	first_name, _sep, last_name = lead.lead_name.partition(" ")
	tenant = frappe.get_doc(
		{
			"doctype": "Tenant",
			"first_name": first_name,
			"last_name": last_name or None,
			"mobile_no": lead.mobile_no,
			"email_id": lead.email_id,
			"gender": lead.gender,
			"occupation": lead.occupation,
		}
	).insert()
	allotment_date = allotment_date or nowdate()
	allotment = api.allot_room(
		tenant.name,
		room,
		allotment_date=allotment_date,
		rent_amount=rent_amount,
		security_deposit=security_deposit,
		deposit_collected=deposit_collected,
		bed_no=bed_no,
		notes=_("Booked through {0}").format(lead.name),
	)

	referrals.on_move_in(lead, tenant.name, allotment)  # before the first invoice, for the friend's discount
	payments = record_token_as_rent(lead, tenant.name, allotment, allotment_date)

	lead.update(
		{
			"status": "Moved In",
			"tenant": tenant.name,
			"allotment": allotment,
			"rent_payment": payments[0] if payments else None,
			"room": room,
			"property": frappe.db.get_value("Tenant Space", room, "property"),
		}
	)
	lead.save()
	return {"tenant": tenant.name, "allotment": allotment, "payments": payments}


def record_token_as_rent(lead, tenant, allotment, allotment_date) -> list[str]:
	"""A paid token becomes rent: the first invoice, and the next one when a short first month
	(moving in late in the month) costs less than the token."""
	left = flt(lead.token_amount) if lead.token_status == "Paid" else 0
	month, payments = get_first_day(allotment_date), []
	while left > 0 and len(payments) < 3:
		invoice = frappe.get_doc(
			{
				"doctype": "Tenant Rent Invoice",
				"tenant_space_allotment": allotment,
				"billing_month": MONTHS[month.month - 1],
				"billing_year": month.year,
				"posting_date": max(getdate(allotment_date), month),
			}
		).insert()
		invoice.submit()
		amount = min(left, flt(invoice.outstanding_amount))
		if amount > 0:
			payment = frappe.get_doc(
				{
					"doctype": "Rent Payment",
					"tenant": tenant,
					"rent_invoice": invoice.name,
					"amount": amount,
					"mode_of_payment": TOKEN_MODES.get(lead.token_mode, "Other"),
					"payment_date": allotment_date,
					"reference_no": lead.token_reference,
					"remarks": _("Booking token paid on {0} ({1})").format(
						frappe.utils.formatdate(lead.token_paid_on), lead.token_mode or "-"
					),
				}
			).insert()
			payment.submit()
			payments.append(payment.name)
			left = flt(left - amount, 2)
		month = add_months(month, 1)
	return payments
