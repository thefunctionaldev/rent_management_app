import frappe

from rent_management.rent_management_system.doctype.rent_property.rent_property import make_slug


def execute():
	"""Each building's address on the listing page, e.g. /stay/sunrise-pg."""
	for name in frappe.get_all("Rent Property", filters={"listing_slug": ("is", "not set")}, pluck="name"):
		frappe.db.set_value(
			"Rent Property", name, "listing_slug", make_slug(name, name), update_modified=False
		)
