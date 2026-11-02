import base64
import binascii
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from rent_management import access, subscription


class SuiteDocument(Document):
	def validate(self):
		if not getattr(frappe.local, "rent_suite_write", False):
			frappe.throw(_("Use the Rent app to change this record."), frappe.PermissionError)
		if self.doctype == "Rent Job Run":
			return
		subscription.check_writable(self)

	def on_trash(self):
		frappe.throw(_("Archive or cancel this record in the Rent app instead."), frappe.PermissionError)


@contextmanager
def service_write():
	previous = getattr(frappe.local, "rent_suite_write", False)
	frappe.local.rent_suite_write = True
	try:
		yield
	finally:
		frappe.local.rent_suite_write = previous


def save(doc):
	with service_write():
		doc.save(ignore_permissions=True)
	return doc


def manager():
	if not access.is_manager():
		frappe.throw(_("Manager access required."), frappe.PermissionError)


def admin():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("System Manager access required."), frappe.PermissionError)


def area(key, property=None):
	if access.is_manager():
		return property
	staff = access.staff_access()
	if not staff or key not in staff.areas:
		frappe.throw(_("Your login does not include this work area."), frappe.PermissionError)
	if staff.building:
		if property and property != staff.building:
			frappe.throw(_("This building is outside your access."), frappe.PermissionError)
		return staff.building
	return property


def scoped(key, property=None):
	prop = area(key, property)
	return {"property": prop} if prop else {}


def locked(doctype, name):
	# Only internal constant DocType names may be passed here.
	frappe.db.sql(f"select name from `tab{doctype}` where name=%s for update", name)
	return frappe.get_doc(doctype, name)


def validate_property(property, room=None):
	if not frappe.db.exists("Rent Property", {"name": property, "is_active": 1}):
		frappe.throw(_("Choose an active building."))
	if room and frappe.db.get_value("Tenant Space", room, "property") != property:
		frappe.throw(_("The room is not in this building."))


def validate_assignee(user, property, key):
	if not user or not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("Choose an active assignee."))
	if access.is_manager(user):
		return
	staff = access.staff_access(user)
	if not staff or key not in staff.areas or (staff.building and staff.building != property):
		frappe.throw(_("The assignee must have access to this area and building."))


def positive(value, allow_zero=False):
	import math

	value = flt(value)
	if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
		frappe.throw(_("Enter a valid positive amount."))
	return value


def own_fields(data, fields):
	data = frappe.parse_json(data) or {}
	return {k: data[k] for k in fields if k in data}


def file_bytes(filename, data):
	try:
		blob = base64.b64decode(data.split(",", 1)[-1], validate=True)
	except (ValueError, binascii.Error, AttributeError):
		frappe.throw(_("Invalid file."))
	if not blob or len(blob) > 5 * 1024 * 1024:
		frappe.throw(_("Files must be smaller than 5 MB."))
	kind = None
	if blob.startswith(b"\x89PNG\r\n\x1a\n"):
		kind = "png"
	elif blob.startswith(b"\xff\xd8\xff"):
		kind = "jpg"
	elif blob.startswith(b"%PDF-"):
		kind = "pdf"
	elif blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
		kind = "webp"
	if not kind:
		frappe.throw(_("Upload a PNG, JPEG, WebP or PDF file."))
	return f"evidence-{frappe.generate_hash(length=10)}.{kind}", blob


def note_failure():
	"""Count a contained per-item failure only while an instrumented job is running."""
	count = getattr(frappe.local, "rent_suite_failures", None)
	if count is not None:
		frappe.local.rent_suite_failures = count + 1
