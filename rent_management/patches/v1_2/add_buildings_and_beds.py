import frappe

from rent_management.rent_management_system.doctype.rent_property.rent_property import get_default_property
from rent_management.rent_management_system.doctype.tenant_space.tenant_space import update_room_occupancy


def execute():
	"""Put existing rooms into a "Main Building", give them one bed each and copy the
	building onto allotments, invoices, payments and settlements."""
	rooms = frappe.get_all("Tenant Space", fields=["name", "property", "capacity"])
	if not rooms:
		return

	default = get_default_property()
	for room in rooms:
		values = {}
		if not room.property:
			values["property"] = default
		if not room.capacity:
			values["capacity"] = 1
		if values:
			frappe.db.set_value("Tenant Space", room.name, values, update_modified=False)

	frappe.db.sql(
		"""update `tabTenant Space Allotment` a join `tabTenant Space` r on r.name = a.room
		set a.property = r.property where ifnull(a.property, '') = ''"""
	)
	frappe.db.sql(
		"""update `tabTenant Space Allotment` set bed_no = 1
		where docstatus = 1 and status = 'Active' and ifnull(bed_no, 0) = 0"""
	)
	for doctype in ("Tenant Rent Invoice", "Security Deposit Settlement"):
		frappe.db.sql(
			f"""update `tab{doctype}` d join `tabTenant Space` r on r.name = d.room
			set d.property = r.property where ifnull(d.property, '') = ''"""
		)
	frappe.db.sql(
		"""update `tabRent Payment` p join `tabTenant Rent Invoice` i on i.name = p.rent_invoice
		set p.property = i.property where ifnull(p.property, '') = ''"""
	)

	for room in rooms:
		update_room_occupancy(room.name)
