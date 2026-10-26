import frappe


def execute():
	"""Requests saved without their building (it was looked up before the room was known)."""
	frappe.db.sql(
		"""
		update `tabMaintenance Request` request
		join `tabTenant Space` room on room.name = request.room
		set request.property = room.property
		where ifnull(request.property, '') = ''
		"""
	)
