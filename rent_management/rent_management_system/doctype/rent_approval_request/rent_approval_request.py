import frappe
from frappe.model.document import Document


class RentApprovalRequest(Document):
	def validate(self):
		if not getattr(frappe.local, "writing_rent_approval", False):
			frappe.throw("Use the Approvals page to manage requests.", frappe.PermissionError)

	def on_trash(self):
		frappe.throw("Approval history cannot be deleted.", frappe.PermissionError)
