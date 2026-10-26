import frappe
from frappe.utils.password import set_encrypted_password


def execute():
	"""Aadhaar numbers used to be stored in plain text: encrypt them, keep the last 4 digits
	for display and move Aadhaar card scans to private files."""
	for tenant in frappe.get_all(
		"Tenant",
		filters={"aadhar_card_number": ("is", "set")},
		fields=["name", "aadhar_card_number"],
	):
		number = str(tenant.aadhar_card_number).replace(" ", "")
		if set(number) == {"*"}:
			continue  # already encrypted
		set_encrypted_password("Tenant", tenant.name, number, "aadhar_card_number")
		frappe.db.set_value(
			"Tenant",
			tenant.name,
			{"aadhar_card_number": "*" * len(number), "aadhar_last4": number[-4:]},
			update_modified=False,
		)

	for tenant in frappe.get_all(
		"Tenant", filters={"aadhar_card": ("like", "/files/%")}, fields=["name", "aadhar_card"]
	):
		for name in frappe.get_all(
			"File", filters={"file_url": tenant.aadhar_card, "is_private": 0}, pluck="name"
		):
			file = frappe.get_doc("File", name)
			file.is_private = 1
			file.flags.ignore_permissions = True
			file.save()
			frappe.db.set_value("Tenant", tenant.name, "aadhar_card", file.file_url, update_modified=False)
