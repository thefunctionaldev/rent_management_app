# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Each tenant's documents in one place: ID, PAN, passport and visa, offer letter, college ID...

Managers (and wardens with rooms and tenants) add them on the tenant's page, and tenants from
the tenant app. Files are private: managers open them directly, tenants through file() after
checking they're theirs. Papers already uploaded elsewhere show here too: the Aadhaar card from
check-in and the police verification of each stay. Managers are told 30 days before a document
expires, and on the day.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

DOCUMENT = "Tenant Document"
TYPES = (
	"PAN Card", "Passport", "Visa", "Driving Licence", "Voter ID", "Aadhaar Card", "Offer Letter",
	"Employee ID", "College ID", "Rental Agreement", "Police Verification", "Other",
)  # fmt: skip
FIELDS = ("document_type", "document_number", "issued_on", "expires_on", "note")


def for_tenant(tenant) -> list[dict]:
	"""The tenant's documents, newest first, with the ones uploaded elsewhere."""
	today = getdate(nowdate())
	rows = [
		{
			**d,
			"key": d.name,
			"editable": True,
			"expired": bool(d.expires_on and getdate(d.expires_on) < today),
			"expiring": bool(d.expires_on and today <= getdate(d.expires_on) <= add_days(today, 30)),
		}
		for d in frappe.get_all(
			DOCUMENT,
			filters={"tenant": tenant},
			fields=[
				"name",
				"document_type",
				"document_number",
				"file",
				"issued_on",
				"expires_on",
				"note",
				"source",
				"creation",
			],
			order_by="creation desc",
		)
	]
	t = frappe.db.get_value("Tenant", tenant, ["aadhar_card", "aadhar_last4"], as_dict=True) or frappe._dict()
	if t.aadhar_card:
		rows.append({"key": "aadhaar", "document_type": "Aadhaar Card", "document_number": f"XXXX XXXX {t.aadhar_last4}" if t.aadhar_last4 else None,
			"file": t.aadhar_card, "source": "Check-in", "editable": False})  # fmt: skip
	for stay in frappe.get_all(
		"Tenant Space Allotment",
		filters={"tenant": tenant, "docstatus": 1},
		fields=[
			"name",
			"room",
			"verification_acknowledgement",
			"verification_copy",
			"verified_on",
			"verification_reference",
		],
	):
		if stay.verification_copy:
			rows.append({"key": f"verified:{stay.name}", "document_type": "Police Verification", "file": stay.verification_copy,
				"issued_on": stay.verified_on, "note": _("Verified, room {0}").format(stay.room), "source": "Verification", "editable": False})  # fmt: skip
		elif stay.verification_acknowledgement:
			rows.append({"key": f"submitted:{stay.name}", "document_type": "Police Verification", "file": stay.verification_acknowledgement,
				"document_number": stay.verification_reference, "note": _("Acknowledgement, room {0}").format(stay.room),
				"source": "Verification", "editable": False})  # fmt: skip
	for row in rows:
		row["is_pdf"] = str(row.get("file") or "").lower().endswith(".pdf")
	return rows


def save(tenant, data, source="Manager") -> str:
	from rent_management import pictures

	data = frappe.parse_json(data)
	if data.get("name"):
		doc = frappe.get_doc(DOCUMENT, data["name"])
		if str(doc.tenant) != str(tenant):
			frappe.throw(_("Document not found."), frappe.PermissionError)
	else:
		doc = frappe.new_doc(DOCUMENT)
		doc.tenant = tenant
		doc.source = source
	if data.get("document_type") not in TYPES and not doc.document_type:
		frappe.throw(_("Choose what the document is."))
	doc.update({f: data.get(f) or None for f in FIELDS if f in data})
	if not doc.file and not data.get("upload"):
		frappe.throw(_("Add a photo or a PDF of the document."))
	doc.flags.ignore_permissions = source == "Tenant App"  # their own, checked by the caller
	doc.save()
	if data.get("upload"):  # attached once the document exists
		pictures.set_document(doc, "file", data["upload"], f"{doc.document_type}-{doc.tenant_name or tenant}")
	return doc.name


def delete(tenant, name):
	doc = frappe.get_doc(DOCUMENT, name)
	if str(doc.tenant) != str(tenant):
		frappe.throw(_("Document not found."), frappe.PermissionError)
	frappe.delete_doc(DOCUMENT, name, ignore_permissions=True)


def send_file(tenant, key):
	"""Stream one of the tenant's files (for the tenant app: private files aren't theirs to open)."""
	row = next((r for r in for_tenant(tenant) if r["key"] == key), None)
	if not row or not row.get("file"):
		frappe.throw(_("Document not found."), frappe.PermissionError)
	file = frappe.get_doc("File", {"file_url": row["file"]})
	frappe.local.response.filename = file.file_name
	frappe.local.response.filecontent = file.get_content(encodings=[])
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "inline"


def remind_expiring():
	"""Daily: managers hear about documents expiring in 30 days, and on the day."""
	from rent_management.portal import notify_managers

	today = getdate(nowdate())
	for when, soon in ((add_days(today, 30), True), (today, False)):
		for d in frappe.get_all(
			DOCUMENT,
			filters={"expires_on": when},
			fields=["name", "tenant", "tenant_name", "document_type", "expires_on"],
		):
			stay = frappe.db.get_value(
				"Tenant Space Allotment", {"tenant": d.tenant, "docstatus": 1, "status": "Active"}, "property"
			)
			if not stay:
				continue  # moved out: no need
			notify_managers(
				(_("{0}'s {1} expires in 30 days") if soon else _("{0}'s {1} expires today")).format(
					d.tenant_name, d.document_type
				),
				_("Ask {0} for the new one.").format(d.tenant_name),
				link=f"/rent/tenants/{d.tenant}",
				area="rooms",
				property=stay,
			)
