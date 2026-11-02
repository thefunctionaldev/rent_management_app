import frappe
from frappe import _

from rent_management import access, portal
from rent_management.suite.common import area, file_bytes, locked, manager, save

TYPES = {
	"Rent Work Order": {"before_photo", "after_photo"},
	"Rent Housekeeping Task": {"photo"},
	"Rent Owner Document": {"file"},
}


def permitted(doc, write=False):
	if access.is_manager():
		return
	if doc.doctype == "Rent Owner Document":
		if write:
			manager()
		from rent_management.suite.owners import check

		check(doc.property)
		return
	if not write and doc.doctype == "Rent Work Order":
		tenant = portal.get_tenant()
		if tenant and str(doc.tenant) == str(tenant) and doc.status in ("Completed", "Confirmed"):
			return
	key = "requests" if doc.doctype == "Rent Work Order" else "housekeeping"
	area(key, doc.property)
	if doc.assigned_to != frappe.session.user:
		frappe.throw(_("This record is assigned to someone else."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def upload(doctype, name, field, filename, data):
	if field not in TYPES.get(doctype, set()):
		frappe.throw(_("Unsupported attachment."))
	doc = locked(doctype, name)
	permitted(doc, write=True)
	if doctype == "Rent Work Order" and (
		doc.status in ("Completed", "Confirmed", "Cancelled")
		or (field == "before_photo" and doc.status not in ("Draft", "Approved", "In Progress"))
	):
		frappe.throw(_("Evidence is locked after completion."))
	if doctype == "Rent Housekeeping Task" and doc.status != "Open":
		frappe.throw(_("Reopen the task before changing its evidence."))
	filename, content = file_bytes(filename, data)
	if doctype != "Rent Owner Document" and filename.endswith(".pdf"):
		frappe.throw(_("Upload a photo for this field."))
	from frappe.utils.file_manager import save_file

	file = save_file(filename, content, doctype, name, is_private=1, df=field)
	doc.set(field, file.file_url)
	save(doc)
	return file.name


@frappe.whitelist()
def download(doctype, name, field):
	if field not in TYPES.get(doctype, set()):
		frappe.throw(_("Unsupported attachment."))
	doc = frappe.get_doc(doctype, name)
	permitted(doc)
	# Mixed tenant/staff logins must still prove staff scope to view before evidence.
	if doctype == "Rent Work Order" and field != "after_photo" and not access.is_manager():
		area("requests", doc.property)
		if doc.assigned_to != frappe.session.user:
			frappe.throw(_("Not permitted."), frappe.PermissionError)
	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": doc.get(field),
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"is_private": 1,
		},
		"name",
	)
	if not file_name:
		frappe.throw(_("File not found."), frappe.DoesNotExistError)
	file = frappe.get_doc("File", file_name)
	frappe.local.response.filename = file.file_name
	frappe.local.response.filecontent = file.get_content()
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "attachment"
