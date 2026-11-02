import frappe
from frappe import _


@frappe.whitelist()
def preference():
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in first."), frappe.PermissionError)
	return "hi" if frappe.db.get_value("User", frappe.session.user, "language") == "hi" else "en"


@frappe.whitelist(methods=["POST"])
def set_preference(language):
	if language not in ("en", "hi") or frappe.session.user == "Guest":
		frappe.throw(_("Choose English or Hindi after signing in."), frappe.PermissionError)
	frappe.db.set_value("User", frappe.session.user, "language", language)
	frappe.clear_cache(user=frappe.session.user)
	return language


def tenant_language(tenant):
	user = frappe.db.get_value("Tenant", tenant, "user")
	return "hi" if user and frappe.db.get_value("User", user, "language") == "hi" else "en"
