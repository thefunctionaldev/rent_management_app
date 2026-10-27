# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Self check-in for new tenants, at /checkin?key=...

The manager sends a link (WhatsApp or email). On their phone, without logging in, the
tenant fills in their details for the records and the police verification, uploads their
Aadhaar card and a photo, reads their rental agreement and signs it with a one-time code.

The code goes to the tenant's email, or on WhatsApp when the site sends WhatsApp messages
(template `rent_signing_code`, category Authentication: "{{1}} is your code to sign your
rental agreement."). What is kept as proof of signing: the agreement exactly as shown, its
SHA-256 fingerprint, the name typed, the time, the IP address and device, and where the
code was sent.
"""

import hashlib
import hmac
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import (
	add_to_date,
	cint,
	get_datetime,
	get_url,
	getdate,
	now_datetime,
	nowdate,
	strip_html,
	validate_email_address,
)

from rent_management import notifications, pictures

CHECKIN = "Tenant Check-in"
ALLOTMENT = "Tenant Space Allotment"
AGREEMENT_FORMAT = "Rent Agreement"
VERIFICATION_FORMAT = "Tenant Verification Form"
CODE_MINUTES = 10
MAX_ATTEMPTS = 5
DETAIL_FIELDS = (
	"first_name",
	"middle_name",
	"last_name",
	"gender",
	"date_of_birth",
	"guardian_name",
	"email_id",
	"permanent_address",
	"occupation",
	"workspace",
	"salary",
	"emergency_contact_name",
	"emergency_contact_relation",
	"emergency_contact_phone",
)
REQUIRED = ("first_name", "gender", "date_of_birth", "guardian_name", "permanent_address")


# ---------------------------------------------------------------- managers


def checkin_url(doc) -> str:
	return get_url(f"/checkin?key={doc.access_key}")


def open_checkin(allotment: str):
	"""The stay's check-in that is still in progress, if any."""
	name = frappe.db.get_value(
		CHECKIN,
		{
			"allotment": allotment,
			"status": ("in", ("Sent", "Details Submitted")),
			"expires_on": (">=", nowdate()),
		},
	)
	return frappe.get_doc(CHECKIN, name) if name else None


def send_checkin(allotment: str) -> dict:
	"""A check-in link for a stay: the open one, or a new one."""
	stay = frappe.get_doc(ALLOTMENT, allotment)
	if stay.docstatus != 1 or stay.status != "Active":
		frappe.throw(_("Only an active stay can be checked in."))
	doc = open_checkin(allotment)
	if not doc:
		doc = frappe.get_doc(
			{"doctype": CHECKIN, "tenant": stay.tenant, "allotment": stay.name, "sent_on": now_datetime()}
		).insert()
	tenant = frappe.db.get_value("Tenant", stay.tenant, ["first_name", "mobile_no", "email_id"], as_dict=True)
	link = checkin_url(doc)
	if tenant.email_id and notifications.email_configured():
		frappe.sendmail(
			recipients=[tenant.email_id],
			subject=_("Complete your check-in at {0}").format(stay.property),
			message=_(
				"<p>Hello {0},</p><p>Welcome! Please fill in your details, upload your ID and sign your "
				"rental agreement here. It takes about 5 minutes:</p><p><a href='{1}'>{1}</a></p>"
			).format(tenant.first_name, link),
		)
	return {"name": doc.name, "url": link, "status": doc.status, "mobile_no": tenant.mobile_no}


def get_status(allotment: str) -> dict | None:
	"""For the tenant's profile: the latest check-in of the stay."""
	rows = frappe.get_all(
		CHECKIN,
		filters={"allotment": allotment, "status": ("!=", "Cancelled")},
		fields=[
			"name",
			"status",
			"sent_on",
			"details_submitted_on",
			"signed_on",
			"signed_name",
			"otp_channel",
			"expires_on",
			"access_key",
		],
		order_by="creation desc",
		limit=1,
	)
	if not rows:
		return None
	row = rows[0]
	expired = row.status != "Signed" and getdate(row.expires_on) < getdate(nowdate())
	row.url = None if (expired or row.status == "Signed") else get_url(f"/checkin?key={row.access_key}")
	row.expired = expired
	row.pop("access_key")
	return row


def signature(allotment: str) -> dict | None:
	"""How the agreement of a stay was signed (for the agreement print)."""
	return frappe.db.get_value(
		CHECKIN,
		{"allotment": allotment, "status": "Signed"},
		["name", "signed_on", "signed_name", "otp_channel", "otp_sent_to", "agreement_hash"],
		as_dict=True,
		order_by="signed_on desc",
	)


# ---------------------------------------------------------------- the tenant's page


def by_key(key):
	name = frappe.db.get_value(CHECKIN, {"access_key": key or "-"})
	if not name:
		raise frappe.DoesNotExistError(_("This check-in link isn't valid."))
	doc = frappe.get_doc(CHECKIN, name)
	if doc.status == "Cancelled":
		raise frappe.DoesNotExistError(
			_("This check-in link was cancelled. Ask your landlord for a new one.")
		)
	if doc.status != "Signed" and getdate(doc.expires_on) < getdate(nowdate()):
		raise frappe.DoesNotExistError(_("This check-in link has expired. Ask your landlord for a new one."))
	return doc


def mask_email(email):
	user, _at, domain = (email or "").partition("@")
	return f"{user[:2]}{'•' * max(len(user) - 2, 1)}@{domain}" if domain else None


def mask_phone(phone):
	digits = "".join(ch for ch in (phone or "") if ch.isdigit())
	return f"••••••{digits[-4:]}" if len(digits) >= 4 else None


def code_channel(tenant) -> tuple[str | None, str | None]:
	"""Where the signing code goes: WhatsApp when the site sends WhatsApp, else email."""
	if notifications.get_whatsapp_account() and notifications.whatsapp_number(tenant.mobile_no):
		return "WhatsApp", mask_phone(tenant.mobile_no)
	if tenant.email_id and notifications.email_configured():
		return "Email", mask_email(tenant.email_id)
	return None, None


def render_agreement(stay) -> str:
	from frappe.www.printview import get_rendered_template

	print_format = frappe.get_doc("Print Format", AGREEMENT_FORMAT)
	frappe.flags.ignore_print_permissions = True  # the check-in key already proves whose stay it is
	try:
		html = get_rendered_template(stay, print_format=print_format)
	finally:
		frappe.flags.ignore_print_permissions = False
	return f"<style>{print_format.css or ''}</style>{html}"


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=300, seconds=60 * 60)
def get_checkin(key=None):
	doc = by_key(key)
	tenant = frappe.get_doc("Tenant", doc.tenant)
	stay = frappe.get_doc(ALLOTMENT, doc.allotment)
	channel, sent_to = code_channel(tenant)
	settings = frappe.get_single("Rent Management Settings")
	return {
		"status": doc.status,
		"tenant": {field: tenant.get(field) for field in DETAIL_FIELDS}
		| {"mobile_no": tenant.mobile_no, "aadhaar_last4": tenant.aadhar_last4},
		"has_aadhaar_card": bool(tenant.aadhar_card),
		"has_photo": bool(tenant.display_picture),
		"stay": {
			"building": frappe.db.get_value("Rent Property", stay.property, "property_name"),
			"room": frappe.db.get_value("Tenant Space", stay.room, "room_number"),
			"bed_no": stay.bed_no,
			"allotment_date": stay.allotment_date,
			"rent_amount": stay.rent_amount,
			"security_deposit": stay.security_deposit,
		},
		"landlord": {"name": settings.landlord_name, "phone": settings.landlord_phone},
		# the agreement shows the tenant's details, so it is only shown once they are in
		"agreement": render_agreement(stay) if doc.status in ("Details Submitted", "Signed") else None,
		"code_channel": channel,
		"code_sent_to": sent_to,
		"signed_on": doc.signed_on,
		"signed_name": doc.signed_name,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def save_details(key=None, details=None, aadhaar_number=None, aadhaar_card=None, photo=None):
	"""Step 1 and 2: the tenant's details, Aadhaar and photo. Images are data URLs."""
	doc = by_key(key)
	if doc.status == "Signed":
		frappe.throw(_("You have already signed. Ask your landlord to change your details."))
	details = frappe.parse_json(details) or {}
	tenant = frappe.get_doc("Tenant", doc.tenant)
	# plain text only: these go into the agreement and the verification form
	values = {
		field: strip_html(value).strip() if isinstance(value, str) else value
		for field, value in details.items()
		if field in DETAIL_FIELDS
	}
	for field in REQUIRED:
		if not (values.get(field) or tenant.get(field)):
			frappe.throw(_("Please fill in {0}.").format(_(tenant.meta.get_label(field))))
	if values.get("email_id") and not validate_email_address(values["email_id"]):
		frappe.throw(_("Please enter a valid email address."))
	if values.get("date_of_birth") and getdate(values["date_of_birth"]) > getdate(
		add_to_date(nowdate(), years=-14)
	):
		frappe.throw(_("Please check your date of birth."))
	if values.get("salary") in ("", None):
		values.pop("salary", None)
	tenant.update(values)
	if aadhaar_number:
		tenant.aadhar_card_number = "".join(ch for ch in aadhaar_number if ch.isdigit())
	if not (tenant.aadhar_last4 or tenant.aadhar_card_number):
		frappe.throw(_("Please enter your Aadhaar number."))
	tenant.flags.ignore_permissions = True
	tenant.save()
	pictures.set_image(tenant, "aadhar_card", aadhaar_card or None, private=True)
	pictures.set_picture(tenant, photo or None)
	if not (tenant.aadhar_card or aadhaar_card):
		frappe.throw(_("Please add a photo of your Aadhaar card."))

	first_time = doc.status == "Sent"
	doc.db_set({"status": "Details Submitted", "details_submitted_on": now_datetime()})
	if first_time:
		notify_managers(doc, _("{0} filled in their check-in details").format(tenant.full_name))
	return get_checkin(key)


def code_hash(doc, code) -> str:
	return hmac.new(doc.access_key.encode(), str(code).encode(), hashlib.sha256).hexdigest()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def send_code(key=None):
	"""A one-time code to sign the agreement."""
	doc = by_key(key)
	if doc.status != "Details Submitted":
		frappe.throw(_("Fill in your details first."))
	tenant = frappe.get_doc("Tenant", doc.tenant)
	channel, sent_to = code_channel(tenant)
	if not channel:
		return {"channel": None}
	code = f"{secrets.randbelow(10**6):06d}"
	if channel == "WhatsApp":
		try:
			notifications.send_whatsapp(
				notifications.whatsapp_number(tenant.mobile_no), "rent_signing_code", [code]
			)
		except Exception:
			frappe.log_error(title=f"Could not send the signing code of {doc.name} on WhatsApp")
			if not (tenant.email_id and notifications.email_configured()):
				frappe.throw(_("The code could not be sent. Please try again in a minute."))
			channel, sent_to = "Email", mask_email(tenant.email_id)
	if channel == "Email":
		frappe.sendmail(
			recipients=[tenant.email_id],
			subject=_("{0} is your code to sign your rental agreement").format(code),
			message=_(
				"<p>Your code to sign your rental agreement is <b>{0}</b>.</p><p>It works for {1} minutes. "
				"If you didn't ask for it, ignore this email.</p>"
			).format(code, CODE_MINUTES),
			now=True,
		)
	doc.db_set(
		{
			"otp_hash": code_hash(doc, code),
			"otp_expires": add_to_date(now_datetime(), minutes=CODE_MINUTES),
			"otp_attempts": 0,
			"otp_channel": channel,
			"otp_sent_to": sent_to,
		}
	)
	return {"channel": channel, "sent_to": sent_to}


def same_name(typed, full_name) -> bool:
	norm = lambda s: " ".join((s or "").lower().split())  # noqa: E731
	return norm(typed) == norm(full_name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def sign(key=None, name=None, agree=0, code=None):
	"""Step 3: sign the agreement by typing their name, ticking the box and entering the code."""
	doc = frappe.get_doc(CHECKIN, by_key(key).name, for_update=True)
	if doc.status == "Signed":
		return get_checkin(key)
	if doc.status != "Details Submitted":
		frappe.throw(_("Fill in your details first."))
	if not cint(agree):
		frappe.throw(_("Please tick that you agree to the agreement."))
	tenant = frappe.get_doc("Tenant", doc.tenant)
	if not same_name(name, tenant.full_name):
		frappe.throw(_("Please type your full name as it appears above: {0}").format(tenant.full_name))

	channel, _sent_to = code_channel(tenant)
	if channel:
		if not doc.otp_hash:
			frappe.throw(_("Ask for a code first."))
		if cint(doc.otp_attempts) >= MAX_ATTEMPTS or get_datetime(doc.otp_expires) < now_datetime():
			frappe.throw(_("This code has expired. Ask for a new one."))
		if not hmac.compare_digest(code_hash(doc, (code or "").strip()), doc.otp_hash):
			doc.db_set("otp_attempts", cint(doc.otp_attempts) + 1)
			if not frappe.flags.in_test:
				frappe.db.commit()  # count the failed attempt even though this request fails
			frappe.throw(_("That code isn't right. Please check it and try again."))

	stay = frappe.get_doc(ALLOTMENT, doc.allotment)
	agreement = render_agreement(stay)
	request = getattr(frappe.local, "request", None)
	doc.update(
		{
			"status": "Signed",
			"signed_on": now_datetime(),
			"signed_name": tenant.full_name,
			"signed_ip": frappe.local.request_ip,
			"user_agent": ((request.headers.get("User-Agent") if request else "") or "")[:500],
			"otp_channel": doc.otp_channel if channel else "None",
			"agreement_snapshot": agreement,
			"agreement_hash": hashlib.sha256(agreement.encode()).hexdigest(),
			"otp_hash": None,
		}
	)
	doc.flags.ignore_permissions = True
	doc.save()
	stay.add_comment(
		"Info",
		_("Rental agreement signed electronically by {0} ({1}).").format(tenant.full_name, doc.name),
	)
	notify_managers(doc, _("{0} signed their rental agreement").format(tenant.full_name))
	return get_checkin(key)


def notify_managers(doc, subject):
	from rent_management.portal import notify_managers as notify

	tenant = frappe.db.get_value("Tenant", doc.tenant, "name")
	notify(subject, subject + ". " + _("See their profile: {0}").format(get_url(f"/rent/tenants/{tenant}")))


# ---------------------------------------------------------------- police verification form


def get_verification_context(doc) -> dict:
	"""For the Tenant Verification Form print (Jinja method). It has the full Aadhaar number,
	which is why printing it is logged on the tenant."""
	import base64

	from rent_management.rent_management_system.doctype.tenant_space_allotment.tenant_space_allotment import (
		get_agreement_context,
	)

	context = get_agreement_context(doc)
	tenant = context["tenant"]
	photo = None
	if tenant.display_picture:
		file = frappe.get_doc("File", {"file_url": tenant.display_picture})
		content = file.get_content(encodings=[])
		mime = "image/png" if tenant.display_picture.endswith(".png") else "image/jpeg"
		photo = f"data:{mime};base64," + base64.b64encode(content).decode()
	number = tenant.get_password("aadhar_card_number", raise_exception=False)
	if number:
		tenant.add_comment(
			"Info", _("Aadhaar number printed in the verification form by {0}").format(frappe.session.user)
		)
	context.update(
		{
			"photo": photo,
			"aadhaar_full": f"{number[:4]} {number[4:8]} {number[8:]}" if number else None,
			"signature": signature(doc.name),
		}
	)
	return context
