import frappe

from rent_management import access
from rent_management.suite.common import area, manager


@frappe.whitelist()
def options(key):
	if key not in ("requests", "expenses", "housekeeping", "leads", "owners"):
		frappe.throw("Unknown work area")
	if key == "owners":
		manager()
		prop = None
	else:
		prop = area(key)
	filters = {"is_active": 1}
	if prop:
		filters["name"] = prop
	properties = frappe.get_all("Rent Property", filters=filters, fields=["name", "property_name"])
	allowed = [p.name for p in properties]
	result = {
		"properties": properties,
		"rooms": frappe.get_all(
			"Tenant Space",
			filters={"property": ["in", allowed]},
			fields=["name", "room_number", "property", "room_type"],
		),
		"manager": access.is_manager(),
	}
	if access.is_manager():
		result["users"] = frappe.get_all(
			"User",
			filters={"enabled": 1, "name": ["not in", ["Guest"]]},
			fields=["name", "full_name"],
			order_by="full_name",
		)
		result["vendors"] = frappe.get_all(
			"Rent Vendor", filters={"is_active": 1}, fields=["name", "vendor_name"]
		)
		result["requests"] = frappe.get_all(
			"Maintenance Request",
			filters={"property": ["in", allowed], "status": ["!=", "Resolved"]},
			fields=["name", "subject", "property", "room"],
			limit_page_length=500,
		)
	return result
