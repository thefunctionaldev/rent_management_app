import frappe
from frappe import _


def protect_expense(doc, method=None):
	"""Paid suite records and their financial evidence must not silently diverge."""
	if doc.is_new():
		return
	linked = any(
		frappe.db.exists(dt, {"expense": doc.name}) for dt in ("Rent Work Order", "Rent Operating Bill")
	)
	if not linked:
		return
	before = doc.get_doc_before_save()
	fields = ("amount", "property", "expense_date", "category", "mode_of_payment", "reference_no", "paid_to")
	if method == "on_trash" or (before and any(before.get(k) != doc.get(k) for k in fields)):
		frappe.throw(
			_(
				"This expense is linked to a paid bill or repair. It cannot be changed or deleted; record a separate correction with an audit note."
			)
		)
