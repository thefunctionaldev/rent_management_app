# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""API for the tenant app at /tenant.

Tenants log in as Website Users with the Rent Tenant role. Every call works out the tenant
from the logged-in user and only ever reads or changes that tenant's own records, so nothing
the browser sends can reach another tenant's data.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate, random_string

from rent_management import (
	documents,
	fees,
	leads,
	mess,
	notices,
	receipts,
	referrals,
	register,
	rent_collection,
	subscription,
)

TENANT_ROLE = "Rent Tenant"
INVOICE = "Tenant Rent Invoice"
REQUEST_FIELDS = [
	"name",
	"subject",
	"category",
	"priority",
	"status",
	"description",
	"resolution",
	"creation",
	"resolved_on",
]


# ---------------------------------------------------------------- access


def get_tenant(user=None) -> str | None:
	user = user or frappe.session.user
	if user == "Guest":
		return None
	return frappe.db.get_value("Tenant", {"user": user})


def current_tenant():
	tenant = get_tenant()
	if not tenant:
		frappe.throw(
			_("Your login isn't linked to a tenant. Ask your landlord to invite you."), frappe.PermissionError
		)
	return frappe.get_doc("Tenant", tenant)


def own_invoice(name: str):
	tenant = current_tenant()
	invoice = frappe.get_doc(INVOICE, name)
	if str(invoice.tenant) != str(tenant.name) or invoice.docstatus != 1:
		frappe.throw(_("Invoice not found."), frappe.PermissionError)
	return invoice


def current_stay(tenant):
	stays = frappe.get_all(
		"Tenant Space Allotment",
		filters={"tenant": tenant, "docstatus": 1, "status": "Active"},
		pluck="name",
		order_by="allotment_date desc",
		limit=1,
	)
	return frappe.get_doc("Tenant Space Allotment", stays[0]) if stays else None


def has_tenant_role(user=None):
	return TENANT_ROLE in frappe.get_roles(user)


def ensure_tenant_role():
	if not frappe.db.exists("Role", TENANT_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": TENANT_ROLE, "desk_access": 0}).insert(
			ignore_permissions=True
		)


# ---------------------------------------------------------------- invites (used by managers)


def invite_tenant(tenant_name: str) -> str:
	"""Create (or reuse) a Website User for the tenant's email and email them a set-password link."""
	ensure_tenant_role()
	tenant = frappe.get_doc("Tenant", tenant_name)
	email = (tenant.email_id or "").strip().lower()
	if not email:
		frappe.throw(_("Add the tenant's email address first. The invite is sent there."))

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if user.user_type == "System User" and not has_tenant_role(email):
			frappe.throw(_("{0} is a staff login. Use a different email for the tenant.").format(email))
		other = frappe.db.get_value("Tenant", {"user": email, "name": ("!=", tenant.name)})
		if other:
			frappe.throw(_("{0} is already the login of another tenant.").format(email))
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": tenant.first_name,
				"last_name": tenant.last_name,
				"mobile_no": tenant.mobile_no,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"new_password": random_string(24),  # never shared; the tenant sets their own
			}
		)
		user.flags.ignore_permissions = True
		user.flags.ignore_password_policy = True
		user.insert()
	user.flags.ignore_permissions = True
	user.add_roles(TENANT_ROLE)
	tenant.db_set("user", user.name)

	link = user._reset_password(send_email=False)
	from rent_management.notifications import email_configured

	if email_configured():
		frappe.sendmail(
			recipients=[email],
			subject=_("Your tenant account"),
			message=_(
				"<p>Hello {0},</p><p>You can now see your rent bills, pay online and raise requests in "
				"the tenant app. Set your password to get started:</p><p><a href='{1}'>{1}</a></p>"
				"<p>After that, log in at <a href='{2}'>{2}</a>. If the link has expired, use "
				"Forgot Password on the login page.</p>"
			).format(tenant.first_name, link, frappe.utils.get_url("/tenant")),
		)
	return link


# ---------------------------------------------------------------- home


@frappe.whitelist()
def get_boot():
	tenant = current_tenant()
	stay = current_stay(tenant.name)
	settings = frappe.get_single("Rent Management Settings")
	building = (
		frappe.db.get_value(
			"Rent Property", stay.property, ["property_name", "address", "city", "image"], as_dict=True
		)
		if stay
		else None
	)
	currency = frappe.db.get_default("currency") or "INR"
	return {
		"tenant": tenant.name,
		"full_name": tenant.full_name,
		"first_name": tenant.first_name,
		"email": tenant.email_id,
		"mobile_no": tenant.mobile_no,
		"picture": picture_url(tenant),
		"building": building,
		"landlord": {
			"name": settings.landlord_name or (building or {}).get("property_name"),
			"phone": settings.landlord_phone,
		},
		"currency": currency,
		"currency_symbol": frappe.db.get_value("Currency", currency, "symbol") or currency,
		"online": rent_collection.get_payment_options(),
		"food": bool(stay and stay.get("meal_plan") and mess.meals_of(stay.property)),
		"referrals": referrals.enabled() and leads.listing_enabled(),
		"notices_unread": len(notices.unread(tenant.name, stay)) if stay else 0,
		"referral_reward": flt(frappe.db.get_single_value("Rent Management Settings", "referral_reward")),
		"read_only": subscription.skip_if_lapsed(),
		"today": nowdate(),
	}


@frappe.whitelist()
def get_home():
	tenant = current_tenant()
	stay = current_stay(tenant.name)
	unpaid = frappe.get_all(
		INVOICE,
		filters={"tenant": tenant.name, "docstatus": 1, "outstanding_amount": (">", 0)},
		fields=[
			"name",
			"billing_month",
			"billing_year",
			"due_date",
			"next_due_date",
			"final_amount",
			"paid_amount",
			"outstanding_amount",
			"late_fee",
			"early_discount_offer",
			"early_discount_until",
			"status",
		],
		order_by="next_due_date asc",
	)
	for invoice in unpaid:
		invoice.pay_now = fees.payable_now(invoice)
	payments = frappe.get_all(
		"Rent Payment",
		filters={"tenant": tenant.name, "docstatus": 1},
		fields=["name", "payment_date", "amount", "mode_of_payment", "rent_invoice"],
		order_by="payment_date desc, creation desc",
		limit=5,
	)
	return {
		"stay": stay_details(stay),
		"due": sum(flt(i.outstanding_amount) for i in unpaid),
		"unpaid": unpaid,
		"payments": payments,
		"pending_confirmation": frappe.db.count("Rent Payment", {"tenant": tenant.name, "docstatus": 0}),
		"open_requests": frappe.db.count(
			"Maintenance Request", {"tenant": tenant.name, "status": ("in", ("Open", "In Progress"))}
		),
		"checkin_url": checkin_link(stay),
		"notice": (notices.unread(tenant.name, stay) or [None])[0] if stay else None,  # the newest unread
	}


def checkin_link(stay):
	"""The check-in the landlord sent, while it isn't finished."""
	from rent_management.checkin import checkin_url, open_checkin

	doc = open_checkin(stay.name) if stay else None
	return checkin_url(doc) if doc else None


def stay_details(stay):
	if not stay:
		return None
	room = frappe.db.get_value("Tenant Space", stay.room, ["room_number", "floor", "capacity"], as_dict=True)
	return {
		"name": stay.name,
		"room": room.room_number,
		"floor": room.floor,
		"bed_no": stay.bed_no if cint(room.capacity) > 1 else None,
		"property": stay.property,
		"allotment_date": stay.allotment_date,
		"rent_amount": stay.rent_amount,
		"security_deposit": stay.security_deposit,
		"deposit_collected": stay.deposit_collected,
		"agreement_end_date": stay.agreement_end_date,
		"notice_period_days": stay.notice_period_days,
		"notice_given_on": stay.notice_given_on,
		"expected_vacate_date": stay.expected_vacate_date,
	}


# ---------------------------------------------------------------- bills


@frappe.whitelist()
def get_invoices():
	tenant = current_tenant()
	return frappe.get_all(
		INVOICE,
		filters={"tenant": tenant.name, "docstatus": 1},
		fields=[
			"name",
			"billing_month",
			"billing_year",
			"due_date",
			"final_amount",
			"paid_amount",
			"outstanding_amount",
			"status",
		],
		order_by="billing_year desc, posting_date desc",
	)


@frappe.whitelist()
def get_invoice(name):
	invoice = own_invoice(name)
	upi = rent_collection.get_upi_link(invoice)
	return {
		"invoice": {
			field: invoice.get(field)
			for field in (
				"name",
				"billing_month",
				"billing_year",
				"from_date",
				"to_date",
				"days_stayed",
				"total_days",
				"due_date",
				"next_due_date",
				"monthly_rent",
				"pro_rated_rent",
				"discount_amount",
				"late_fee",
				"early_discount",
				"early_discount_offer",
				"early_discount_until",
				"final_amount",
				"paid_amount",
				"outstanding_amount",
				"status",
				"room",
			)
		},
		"charges": [
			{"charge_type": c.charge_type, "description": c.description, "amount": c.amount}
			for c in invoice.charges
		],
		"payments": frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": invoice.name, "docstatus": 1},
			fields=["name", "payment_date", "amount", "mode_of_payment", "reference_no"],
			order_by="payment_date asc",
		),
		"pending": frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": invoice.name, "docstatus": 0},
			fields=["name", "payment_date", "amount", "mode_of_payment", "reference_no"],
		),
		"pay_now": fees.payable_now(invoice),
		"discount_now": fees.discount_available(invoice),
		"instalments": fees.schedule(invoice),
		"upi_link": upi,
		"upi_qr": rent_collection.qr_data_uri(upi) if upi else None,
		"upi_id": frappe.db.get_single_value("Rent Management Settings", "upi_id"),
		"online": rent_collection.get_payment_options(),
	}


@frappe.whitelist(methods=["POST"])
def pay_online(name):
	"""The Razorpay payment link for the invoice's balance."""
	invoice = own_invoice(name)
	if subscription.skip_if_lapsed():
		frappe.throw(_("Online payment is paused. Please pay your landlord directly."))
	return rent_collection.get_payment_link(invoice.name)


@frappe.whitelist(methods=["POST"])
def check_payment(name):
	"""After coming back from the payment page: record what was paid."""
	invoice = own_invoice(name)
	recorded = rent_collection.sync_payment_link(invoice)
	return {
		"recorded": len(recorded),
		"outstanding": frappe.db.get_value(INVOICE, invoice.name, "outstanding_amount"),
	}


@frappe.whitelist(methods=["POST"])
def report_payment(name, amount, reference_no=None, payment_date=None, mode_of_payment="UPI"):
	"""'I've paid': saved as a draft Rent Payment that the landlord confirms."""
	invoice = own_invoice(name)
	if mode_of_payment not in ("UPI", "Bank Transfer", "Cash", "Cheque", "Other"):
		frappe.throw(_("Choose how you paid."))
	payment = frappe.get_doc(
		{
			"doctype": "Rent Payment",
			"tenant": invoice.tenant,
			"rent_invoice": invoice.name,
			"amount": flt(amount),
			"mode_of_payment": mode_of_payment,
			"payment_date": payment_date or nowdate(),
			"reference_no": (reference_no or "").strip()[:140] or None,
			"remarks": _(
				"Reported by the tenant in the tenant app. Check it reached you, then submit to confirm."
			),
		}
	)
	payment.flags.ignore_permissions = True
	frappe.flags.recording_online_payment = True  # the tenant can still report payments on a lapsed site
	try:
		payment.insert()
	finally:
		frappe.flags.recording_online_payment = False
	notify_managers(
		_("{0} says they paid {1} for {2}").format(
			invoice.tenant_name,
			frappe.utils.fmt_money(payment.amount, currency="INR"),
			f"{invoice.billing_month} {invoice.billing_year}",
		),
		_("Reference: {0}. Confirm it in Payments once it has reached you.").format(
			payment.reference_no or "-"
		),
		link="/rent/payments",
		area="payments",
		property=invoice.property,
	)
	return payment.name


def picture_url(tenant) -> str | None:
	# the photo is a private file the tenant can't open directly; the version busts the cache
	if not tenant.display_picture:
		return None
	version = hashlib.sha1(tenant.display_picture.encode()).hexdigest()[:8]
	return f"/api/method/rent_management.portal.my_picture?v={version}"


@frappe.whitelist()
def my_picture():
	tenant = current_tenant()
	if not tenant.display_picture:
		raise frappe.DoesNotExistError
	file = frappe.get_doc("File", {"file_url": tenant.display_picture})
	frappe.local.response.filename = file.file_name
	frappe.local.response.filecontent = file.get_content(encodings=[])  # bytes, not decoded text
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "inline"


@frappe.whitelist(methods=["POST"])
def update_picture(picture=None):
	"""The tenant sets or removes their own photo (a data URL, or "" to remove)."""
	from rent_management.pictures import set_picture

	tenant = current_tenant()
	subscription.check_writable()
	set_picture(tenant, picture or "")
	tenant.reload()
	return picture_url(tenant)


@frappe.whitelist()
def download_invoice(name):
	invoice = own_invoice(name)
	send_print(INVOICE, invoice.name, "Tenant Rent Invoice Print Format", f"Rent-{invoice.name}")


@frappe.whitelist()
def download_agreement():
	tenant = current_tenant()
	stay = current_stay(tenant.name)
	if not stay:
		frappe.throw(_("You have no current stay."))
	send_print("Tenant Space Allotment", stay.name, "Rent Agreement", f"Agreement-{stay.name}")


def send_print(doctype, name, print_format, filename):
	frappe.flags.ignore_print_permissions = True  # ownership is checked by the caller
	try:
		content = frappe.get_print(doctype, name, print_format=print_format, as_pdf=True)
	finally:
		frappe.flags.ignore_print_permissions = False
	frappe.local.response.filename = f"{filename}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"


# ---------------------------------------------------------------- requests


@frappe.whitelist()
def get_requests():
	tenant = current_tenant()
	return frappe.get_all(
		"Maintenance Request",
		filters={"tenant": tenant.name},
		fields=REQUEST_FIELDS,
		order_by="creation desc",
	)


@frappe.whitelist(methods=["POST"])
def create_request(subject, category, description=None, priority="Medium"):
	tenant = current_tenant()
	meta = frappe.get_meta("Maintenance Request")
	if category not in meta.get_field("category").options.split("\n"):
		frappe.throw(_("Choose a category."))
	if priority not in ("Low", "Medium", "High"):
		priority = "Medium"
	request = frappe.get_doc(
		{
			"doctype": "Maintenance Request",
			"tenant": tenant.name,
			"subject": (subject or "").strip()[:140],
			"category": category,
			"priority": priority,
			"description": description,
			"raised_via": "Tenant App",
		}
	)
	request.flags.ignore_permissions = True
	request.insert()
	notify_managers(
		_("New request from {0}: {1}").format(tenant.full_name, request.subject),
		_("Room {0} · {1} · {2} priority").format(request.room or "-", category, priority),
		link="/rent/requests",
		area="requests",
		property=request.get("property"),
	)
	return request.name


# ---------------------------------------------------------------- notice


@frappe.whitelist(methods=["POST"])
def give_notice(vacate_date=None):
	tenant = current_tenant()
	stay = current_stay(tenant.name)
	if not stay:
		frappe.throw(_("You have no current stay."))
	if stay.expected_vacate_date:
		frappe.throw(_("You have already given notice."))
	stay.flags.ignore_permissions = True  # tenants can't write allotments; this is their own stay
	result = stay.give_notice(nowdate(), vacate_date)
	notify_managers(
		_("{0} gave notice").format(tenant.full_name),
		_("Room {0}, moving out on {1}.").format(
			stay.room, frappe.utils.formatdate(result["expected_vacate_date"])
		),
		link=f"/rent/tenants/{tenant.name}",
		area="rooms",
		property=stay.property,
	)
	return result


def notify_managers(subject, message, link=None, area=None, property=None):
	"""An email and an app notification (and a phone notification, see pwa.py) to every manager,
	and to the staff logins for that area (and building). `link` is the page in the manager app
	it opens, like /rent/register?tab=leave."""
	from rent_management import access
	from rent_management.notifications import email_configured

	recipients = subscription.get_manager_users()
	if area:
		recipients += [u for u in access.staff_users(area, property) if u not in recipients]
	if recipients and email_configured():
		frappe.sendmail(recipients=recipients, subject=subject, message=f"<p>{message}</p>")
	for user in recipients:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": message,
				"link": link,
			}
		).insert(ignore_permissions=True)


# ---------------------------------------------------------------- food


@frappe.whitelist()
def get_food():
	stay = current_stay(current_tenant().name)
	if not (stay and stay.get("meal_plan")):
		frappe.throw(_("You don't have a meal plan."))
	return mess.tenant_week(stay)


@frappe.whitelist(methods=["POST"])
def skip_meal(date, meal, skip=1):
	stay = current_stay(current_tenant().name)
	if not stay:
		frappe.throw(_("You have no current stay."))
	subscription.check_writable()
	mess.set_skip(stay.name, date, meal, cint(skip))
	return mess.tenant_week(stay)


# ---------------------------------------------------------------- leave and visitors


def my_stay():
	tenant = current_tenant()
	stay = current_stay(tenant.name)
	if not stay:
		frappe.throw(_("You have no current stay."))
	return tenant, stay


@frappe.whitelist()
def get_register():
	tenant, stay = my_stay()
	building = frappe.db.get_value(
		"Rent Property", stay.property, ["curfew_time", "visitors_until"], as_dict=True
	)
	return {
		"curfew": str(building.curfew_time)[:5] if building.curfew_time else None,
		"visitors_until": str(building.visitors_until)[:5] if building.visitors_until else None,
		"leaves": frappe.get_all(
			register.LEAVE,
			filters={"allotment": stay.name, "to_date": (">=", add_days(nowdate(), -60))},
			fields=["name", "from_date", "to_date", "status", "destination", "reason", "decision_note"],
			order_by="from_date desc",
		),
		"visitors": frappe.get_all(
			register.VISITOR,
			filters={
				"tenant": tenant.name,
				"property": stay.property,
				"creation": (">=", add_days(nowdate(), -30)),
			},
			fields=[
				"name",
				"visitor_name",
				"visitor_phone",
				"purpose",
				"status",
				"expected_on",
				"check_in",
				"check_out",
				"overnight",
			],
			order_by="creation desc",
			limit=20,
		),
	}


@frappe.whitelist(methods=["POST"])
def request_leave(from_date, to_date, destination=None, reason=None):
	_tenant, stay = my_stay()
	subscription.check_writable()
	register.request_leave(stay.name, from_date, to_date, destination, reason)
	return get_register()


@frappe.whitelist(methods=["POST"])
def cancel_leave(name):
	_tenant, stay = my_stay()
	leave = frappe.db.get_value(register.LEAVE, name, ["allotment", "status", "from_date"], as_dict=True)
	if not leave or leave.allotment != stay.name:
		frappe.throw(_("Leave not found."), frappe.PermissionError)
	if leave.status not in ("Requested", "Approved"):
		frappe.throw(_("This leave can't be cancelled."))
	register.cancel_leave(name)
	return get_register()


@frappe.whitelist(methods=["POST"])
def expect_visitor(visitor_name, expected_on, visitor_phone=None, purpose=None, overnight=0):
	tenant, stay = my_stay()
	subscription.check_writable()
	register.expect_visitor(tenant.name, stay, visitor_name, expected_on, visitor_phone, purpose, overnight)
	return get_register()


@frappe.whitelist(methods=["POST"])
def cancel_visitor(name):
	tenant, _stay = my_stay()
	visitor = frappe.db.get_value(register.VISITOR, name, ["tenant", "status"], as_dict=True)
	if not visitor or str(visitor.tenant) != str(tenant.name) or visitor.status != "Expected":
		frappe.throw(_("Visitor not found."), frappe.PermissionError)
	frappe.db.set_value(register.VISITOR, name, "status", "Cancelled")
	return get_register()


# ---------------------------------------------------------------- referrals


@frappe.whitelist()
def get_referral():
	tenant = current_tenant()
	if not (referrals.enabled() and leads.listing_enabled()):
		frappe.throw(_("Referrals aren't on."))
	return referrals.for_tenant(tenant.name)


# ---------------------------------------------------------------- notice board


@frappe.whitelist()
def get_notices():
	"""The notice board; opening it marks them seen."""
	tenant, stay = my_stay()
	rows = notices.for_tenant(tenant.name, stay)
	notices.mark_read(tenant.name, [r.name for r in rows if r.unread])
	return rows


# ---------------------------------------------------------------- rent receipts for income tax


@frappe.whitelist()
def get_rent_receipts(fy=None):
	return receipts.summary(current_tenant().name, fy)


@frappe.whitelist()
def download_rent_receipt(fy, invoice=None):
	tenant = current_tenant()
	if invoice:
		own_invoice(invoice)  # their own
	receipts.send_pdf(tenant.name, fy, invoice)


# ---------------------------------------------------------------- documents


@frappe.whitelist()
def get_documents():
	tenant = current_tenant()
	return {"documents": documents.for_tenant(tenant.name), "types": documents.TYPES}


@frappe.whitelist(methods=["POST"])
def save_document(data):
	tenant = current_tenant()
	subscription.check_writable()
	data = frappe.parse_json(data)
	if data.get("name") and frappe.db.get_value(documents.DOCUMENT, data["name"], "source") != "Tenant App":
		frappe.throw(_("Ask your landlord to change this one."), frappe.PermissionError)
	documents.save(tenant.name, data, source="Tenant App")
	return get_documents()


@frappe.whitelist(methods=["POST"])
def delete_document(name):
	tenant = current_tenant()
	if frappe.db.get_value(documents.DOCUMENT, name, "source") != "Tenant App":
		frappe.throw(_("Ask your landlord to remove this one."), frappe.PermissionError)
	documents.delete(tenant.name, name)
	return get_documents()


@frappe.whitelist()
def document_file(key):
	documents.send_file(current_tenant().name, key)
