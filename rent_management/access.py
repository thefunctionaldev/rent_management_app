# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Staff logins with limited access.

A manager gives a staff member (a warden, a cook, an accountant) a login to the manager app,
for the areas of work they do (AREAS) and, if set, only their building. Managers (Rent
Manager, System Manager) can do everything; staff (Rent Staff, no Desk) only their areas.

It is enforced on the server three ways:
- every endpoint in api.py calls check_access(), which knows the endpoint (the caller) and
  allows it for staff only when it's in ENDPOINTS for one of their areas. Endpoints not listed
  (profit, salaries, settings, billing, Aadhaar numbers...) are for managers only.
- a staff member limited to a building must ask for that building in endpoints that take one.
- DocType permissions (has_permission and permission_query_conditions hooks), for the records
  the Rent Staff role can open through Frappe's own APIs: only in their areas and building.
"""

import sys

import frappe
from frappe import _

MANAGER_ROLES = ("System Manager", "Rent Manager")
STAFF_ROLE = "Rent Staff"
STAFF = "Staff Member"

# what a staff login can be given, in the order shown
AREAS = {
	"rooms": _("Rooms and tenants"),
	"payments": _("Rent and payments"),
	"register": _("Night attendance, leave and visitors"),
	"requests": _("Requests and repairs"),
	"food": _("Food and menu"),
	"leads": _("Leads and bookings"),
	"meters": _("Electricity readings"),
	"expenses": _("Expenses"),
	"notices": _("Notice board"),
}
PRESETS = {
	"Warden": ["rooms", "payments", "register", "requests", "meters", "notices"],
	"Cook": ["food"],
	"Security Guard": ["register"],
	"Cleaner": ["requests"],
	"Maintenance": ["requests", "meters"],
	"Manager": list(AREAS),
}

# api.py endpoints staff may use, by area ("any" for every staff login)
ENDPOINTS = {
	"any": ("get_boot", "get_properties", "get_room_types", "get_staff_home"),
	"rooms": (
		"get_rooms", "get_room_items", "get_tenants", "quick_search", "get_tenant", "save_tenant", "allot_room",
		"vacate_room", "give_notice", "withdraw_notice", "get_renewal", "renew_agreement",
		"send_renewal_for_signing", "download_agreement", "mark_deposit_collected",
		"invite_tenant", "send_checkin", "get_room_inspection", "save_room_inspection",
		"get_checklist_deductions", "get_billable_allotments", "get_rent_receipts", "download_rent_receipt",
		"get_verifications", "update_verification", "track_verification", "download_verification_form",
		"get_tenant_documents", "save_tenant_document", "delete_tenant_document",
	),
	"payments": (
		"get_tenants", "quick_search", "get_tenant", "get_invoices", "get_invoice", "get_payments", "record_payment",
		"get_payments_to_confirm", "confirm_payment", "reject_payment", "send_rent_reminder",
		"get_reminder_list", "send_bulk_reminders", "mark_invoices_paid",
		"get_payment_link", "check_online_payment", "get_outstanding", "get_cash_book", "hand_over_cash",
		"get_rent_receipts", "download_rent_receipt", "get_tenant_statement", "download_tenant_statement",
		"download_no_dues",
		"confirm_cash_handover", "cancel_cash_handover",
	),
	"register": (
		"get_register", "save_attendance", "add_leave", "decide_leave", "cancel_leave", "visitor_in",
		"visitor_out", "cancel_visitor",
	),
	"requests": ("get_requests", "save_request"),
	"food": ("get_food", "save_menu", "set_meal_plan", "skip_meal_for"),
	"leads": ("get_leads", "get_lead", "save_lead", "record_lead_token", "ask_lead_for_token", "move_in_lead", "get_rooms", "download_listing_poster"),
	"meters": ("get_meter_rooms", "save_meter_readings", "get_meter_readings", "delete_meter_reading"),
	"expenses": ("get_expenses", "save_expense", "get_cash_book", "hand_over_cash", "confirm_cash_handover", "cancel_cash_handover"),
	"notices": ("get_notices", "save_notice", "publish_notice", "take_down_notice", "delete_notice"),
}  # fmt: skip

# records the Rent Staff role can open, and the areas that need them
DOCTYPES = {
	"Tenant": ("rooms", "payments", "register", "leads", "food"),
	"Tenant Space Allotment": ("rooms", "payments", "register", "leads", "food"),
	"Tenant Space": ("rooms", "leads", "meters", "register"),
	"Room Inspection": ("rooms",),
	"Tenant Check-in": ("rooms",),
	"Tenant Rent Invoice": ("payments", "rooms", "meters"),
	"Rent Payment": ("payments", "leads"),
	"Night Attendance": ("register",),
	"Tenant Leave": ("register",),
	"Visitor Log": ("register",),
	"Meal Opt-out": ("food", "register"),
	"Mess Menu": ("food",),
	"Maintenance Request": ("requests",),
	"Rent Lead": ("leads",),
	"Meter Reading": ("meters",),
	"Property Expense": ("expenses",),
	"Rent Notice": ("notices",),
	"Tenant Document": ("rooms",),
}


# ---------------------------------------------------------------- who is this


def is_manager(user=None) -> bool:
	return bool(set(frappe.get_roles(user)) & set(MANAGER_ROLES))


def staff_access(user=None) -> frappe._dict | None:
	"""A staff login's areas and building; None for managers and everyone else."""
	user = user or frappe.session.user
	if user in ("Administrator", "Guest") or is_manager(user) or STAFF_ROLE not in frappe.get_roles(user):
		return None
	# once per request (frappe.local is new for each)
	cache = getattr(frappe.local, "rent_staff_access", None)
	if cache is None:
		cache = frappe.local.rent_staff_access = {}
	if user not in cache:
		staff = frappe.db.get_value(
			STAFF,
			{"user": user},
			["name", "staff_name", "property", "app_areas", "app_all_buildings", "is_active"],
			as_dict=True,
		)
		if not staff or not staff.is_active:
			cache[user] = frappe._dict(areas=set(), building=None, staff=None)
		else:
			cache[user] = frappe._dict(
				areas=set(filter(None, (staff.app_areas or "").split(","))) & set(AREAS),
				building=None if staff.app_all_buildings else staff.property,
				staff=staff.name,
				staff_name=staff.staff_name,
			)
	return cache[user]


def allowed_endpoints(access) -> set[str]:
	names = set(ENDPOINTS["any"])
	for area in access.areas:
		names.update(ENDPOINTS.get(area, ()))
	return names


# ---------------------------------------------------------------- endpoints


def check_access(endpoint=None):
	"""Called first thing by every endpoint in api.py (the caller is the endpoint)."""
	user = frappe.session.user
	if is_manager(user):
		return
	access = staff_access(user)
	if access is None:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	caller = sys._getframe(2) if endpoint is None else None  # api.check_access -> here
	name = endpoint or caller.f_code.co_name
	if name not in allowed_endpoints(access):
		frappe.throw(_("Your login doesn't include this. Ask your manager."), frappe.PermissionError)
	if (
		access.building
		and caller is not None
		and "property" in caller.f_code.co_varnames[: caller.f_code.co_argcount]
	):
		asked = caller.f_locals.get("property")
		if asked != access.building:
			frappe.throw(_("Your login is for {0} only.").format(access.building), frappe.PermissionError)


# ---------------------------------------------------------------- records (DocType permissions)


def has_permission(doc, ptype=None, user=None, debug=False):
	"""A veto on top of the role permissions: True means no objection (Frappe denies on falsy)."""
	access = staff_access(user)
	if access is None:
		return True
	if doc.doctype == "Cash Handover":  # their own only
		return (user or frappe.session.user) in (doc.from_user, doc.to_user)
	if not access.areas & set(DOCTYPES.get(doc.doctype, ())):
		return False
	building = doc.get("property") if doc.meta.has_field("property") else None
	return not (access.building and building and building != access.building)


def query_conditions(user=None, doctype=None):
	access = staff_access(user)
	if access is None or not doctype:
		return ""
	if doctype == "Cash Handover":  # their own only
		me = frappe.db.escape(user or frappe.session.user)
		return f"(`tabCash Handover`.`from_user` = {me} or `tabCash Handover`.`to_user` = {me})"
	if not access.areas & set(DOCTYPES.get(doctype, ())):
		return "1=0"
	if access.building and frappe.get_meta(doctype).has_field("property"):
		return f"`tab{doctype}`.`property` = {frappe.db.escape(access.building)}"
	return ""


# ---------------------------------------------------------------- giving logins


def ensure_role():
	if not frappe.db.exists("Role", STAFF_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": STAFF_ROLE, "desk_access": 0}).insert(
			ignore_permissions=True
		)


def give_login(staff_name, email, areas, all_buildings=0) -> dict:
	"""Give a staff member a login (or change what it can do). For a new login, returns the link
	to set their password (and emails it)."""
	from frappe.utils import random_string, validate_email_address

	ensure_role()
	staff = frappe.get_doc(STAFF, staff_name)
	email = (email or "").strip().lower()
	if not validate_email_address(email):
		frappe.throw(_("Enter their email address. Their login link is sent there."))
	areas = [a for a in (frappe.parse_json(areas) if isinstance(areas, str) else areas) if a in AREAS]
	if not areas:
		frappe.throw(_("Choose at least one thing they can do."))
	if staff.user and staff.user != email:
		remove_login(staff_name)
		staff.reload()

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if is_manager(email) or frappe.db.exists("Tenant", {"user": email}):
			frappe.throw(
				_("{0} is already a manager's or a tenant's login. Use another email.").format(email)
			)
		other = frappe.db.get_value(STAFF, {"user": email, "name": ("!=", staff.name)}, "staff_name")
		if other:
			frappe.throw(_("{0} is already {1}'s login.").format(email, other))
		user.enabled = 1
	else:
		first, _sep, last = staff.staff_name.partition(" ")
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first,
				"last_name": last or None,
				"mobile_no": staff.mobile_no or None,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"new_password": random_string(24),  # never shared; they set their own
			}
		)
	user.flags.ignore_permissions = True
	user.flags.ignore_password_policy = True
	user.save() if not user.is_new() else user.insert()
	user.add_roles(STAFF_ROLE)
	new_login = staff.user != user.name
	staff.db_set(
		{
			"user": user.name,
			"app_areas": ",".join(areas),
			"app_all_buildings": 1 if int(all_buildings or 0) else 0,
		}
	)
	frappe.local.rent_staff_access = {}
	from rent_management import activity

	what = ", ".join(str(AREAS[a]).lower() for a in areas)
	activity.log(
		"Staff",
		(
			_("gave {0} a login ({1}) for {2}") if new_login else _("changed the login of {0} ({1}) to {2}")
		).format(staff.staff_name, user.name, what),
		staff,
	)
	if not new_login:
		return {"user": user.name, "link": None}  # only what they can do changed

	link = user._reset_password(send_email=False)
	from rent_management.notifications import email_configured

	if email_configured():
		frappe.sendmail(
			recipients=[email],
			subject=_("Your login to {0}").format(
				frappe.db.get_value("Rent Property", staff.property, "property_name")
			),
			message=_(
				"<p>Hello {0},</p><p>You now have a login to the manager app. Set your password here:</p>"
				"<p><a href='{1}'>{1}</a></p><p>Then open <a href='{2}'>{2}</a> on your phone and add it to "
				"your home screen.</p>"
			).format(staff.staff_name.split(" ")[0], link, frappe.utils.get_url("/rent")),
		)
	return {"user": user.name, "link": link}


def remove_login(staff_name):
	staff = frappe.get_doc(STAFF, staff_name)
	if not staff.user:
		return
	if frappe.db.exists("User", staff.user):
		user = frappe.get_doc("User", staff.user)
		user.flags.ignore_permissions = True
		user.remove_roles(STAFF_ROLE)
		if not set(frappe.get_roles(user.name)) - {"All", "Guest"}:
			user.reload()
			user.enabled = 0  # nothing else to log in for
			user.save(ignore_permissions=True)
		from frappe.sessions import clear_sessions

		clear_sessions(user.name, force=True)
	staff.db_set({"user": None, "app_areas": None})
	frappe.local.rent_staff_access = {}
	from rent_management import activity

	activity.log("Staff", _("removed the login of {0}").format(staff.staff_name), staff)


def staff_users(area, property=None) -> list[str]:
	"""Staff logins for an area (and building), to notify along with managers."""
	users = []
	for staff in frappe.get_all(
		STAFF,
		filters={"user": ("is", "set"), "is_active": 1},
		fields=["user", "app_areas", "property", "app_all_buildings"],
	):
		if area not in (staff.app_areas or "").split(","):
			continue
		if property and not staff.app_all_buildings and staff.property != property:
			continue
		users.append(staff.user)
	return users
