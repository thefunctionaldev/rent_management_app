# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def make_property(name=None):
	name = name or "Test Building " + frappe.generate_hash(length=6)
	if not frappe.db.exists("Rent Property", name):
		frappe.get_doc(
			{"doctype": "Rent Property", "property_name": name, "abbr": frappe.generate_hash(length=4)}
		).insert()
	return name


def make_room(rent=3000, deposit=None, capacity=1, property=None, room_number=None):
	room_type = frappe.get_doc(
		{
			"doctype": "Tenant Space Type",
			"type": "Test Type " + frappe.generate_hash(length=6),
			"standard_rent": rent,
			"deposit_applicable": 1 if deposit else 0,
			"security_deposit": deposit,
		}
	).insert()
	return frappe.get_doc(
		{
			"doctype": "Tenant Space",
			"room_number": room_number or "T-" + frappe.generate_hash(length=6),
			"floor": "Ground",
			"room_type": room_type.name,
			"capacity": capacity,
			"property": property,
		}
	).insert()


def make_tenant():
	return frappe.get_doc({"doctype": "Tenant", "first_name": "Test", "last_name": "Tenant"}).insert()


def make_allotment(room=None, tenant=None, allotment_date="2026-01-01", submit=True, **kwargs):
	allotment = frappe.get_doc(
		{
			"doctype": "Tenant Space Allotment",
			"tenant": (tenant or make_tenant()).name,
			"room": (room or make_room()).name,
			"allotment_date": allotment_date,
			**kwargs,
		}
	).insert()
	if submit:
		allotment.submit()
	return allotment


class IntegrationTestTenantSpaceAllotment(IntegrationTestCase):
	def test_rent_and_deposit_from_room(self):
		room = make_room(rent=4500, deposit=9000)
		allotment = make_allotment(room=room, submit=False)
		self.assertEqual(allotment.rent_amount, 4500)
		self.assertEqual(allotment.security_deposit, 9000)
		self.assertEqual(allotment.status, "Draft")

	def test_submit_occupies_room(self):
		allotment = make_allotment()
		self.assertEqual(allotment.status, "Active")
		room = frappe.get_doc("Tenant Space", allotment.room)
		self.assertEqual(room.status, "Occupied")
		self.assertEqual(str(room.tenant), str(allotment.tenant))
		self.assertEqual(room.current_allotment, allotment.name)

	def test_room_cannot_be_allotted_twice(self):
		allotment = make_allotment()
		room = frappe.get_doc("Tenant Space", allotment.room)
		self.assertRaises(frappe.ValidationError, make_allotment, room=room)

	def test_vacate_frees_room(self):
		allotment = make_allotment()
		self.assertRaises(frappe.ValidationError, allotment.vacate, "2025-12-31")

		allotment.vacate("2026-02-15")
		allotment.reload()
		self.assertEqual(allotment.status, "Vacated")
		self.assertEqual(str(allotment.vacate_date), "2026-02-15")
		self.assertEqual(frappe.db.get_value("Tenant Space", allotment.room, "status"), "Available")

		# room can now be allotted again
		make_allotment(room=frappe.get_doc("Tenant Space", allotment.room), allotment_date="2026-03-01")

	def test_cancel_frees_room(self):
		allotment = make_allotment()
		allotment.cancel()
		self.assertEqual(allotment.status, "Cancelled")
		room = frappe.get_doc("Tenant Space", allotment.room)
		self.assertEqual(room.status, "Available")
		self.assertFalse(room.tenant)


class IntegrationTestBedsAndBuildings(IntegrationTestCase):
	def test_shared_room(self):
		room = make_room(capacity=3)
		first = make_allotment(room=room)
		self.assertEqual(first.bed_no, 1)
		room.reload()
		self.assertEqual((room.status, room.occupied_beds), ("Partly Occupied", 1))
		self.assertEqual(room.current_allotment, first.name)

		second = make_allotment(room=room, bed_no=3)
		third = make_allotment(room=room)
		self.assertEqual((second.bed_no, third.bed_no), (3, 2))
		room.reload()
		self.assertEqual((room.status, room.occupied_beds), ("Occupied", 3))
		self.assertFalse(room.current_allotment)  # several tenants: no single "current" one

		# full
		self.assertRaises(frappe.ValidationError, make_allotment, room=room)

		second.vacate("2026-02-01")
		room.reload()
		self.assertEqual((room.status, room.occupied_beds), ("Partly Occupied", 2))
		# the freed bed is reused
		self.assertEqual(make_allotment(room=room, allotment_date="2026-02-02").bed_no, 3)

	def test_bed_checks(self):
		room = make_room(capacity=2)
		tenant = make_tenant()
		make_allotment(room=room, tenant=tenant, bed_no=1)
		self.assertRaises(frappe.ValidationError, make_allotment, room=room, bed_no=1)
		self.assertRaises(frappe.ValidationError, make_allotment, room=room, bed_no=5)
		# same tenant can't take a second bed in the same room
		self.assertRaises(frappe.ValidationError, make_allotment, room=room, tenant=tenant)

	def test_capacity_cannot_drop_below_tenants(self):
		room = make_room(capacity=2)
		make_allotment(room=room)
		make_allotment(room=room)
		room.reload()
		room.capacity = 1
		self.assertRaises(frappe.ValidationError, room.save)

		room.reload()
		room.capacity = 3
		room.save()
		self.assertEqual(room.status, "Partly Occupied")

	def test_same_room_number_in_two_buildings(self):
		number = "R-" + frappe.generate_hash(length=5)
		first = make_room(property=make_property(), room_number=number)
		other = make_property()
		second = make_room(property=other, room_number=number)
		self.assertEqual(first.name, number)
		self.assertEqual(second.name, f"{number}-{frappe.db.get_value('Rent Property', other, 'abbr')}")
		# but not twice in the same building
		self.assertRaises(frappe.ValidationError, make_room, property=other, room_number=number)

	def test_building_flows_to_invoices_and_payments(self):
		building = make_property()
		allotment = make_allotment(room=make_room(property=building))
		self.assertEqual(allotment.property, building)
		invoice = frappe.get_doc(
			{
				"doctype": "Tenant Rent Invoice",
				"tenant_space_allotment": allotment.name,
				"billing_month": "January",
				"billing_year": 2026,
				"posting_date": "2026-01-01",
			}
		).insert()
		self.assertEqual(invoice.property, building)

	def test_migration_patch(self):
		from rent_management.patches.v1_2 import add_buildings_and_beds

		allotment = make_allotment()
		frappe.db.set_value(
			"Tenant Space", allotment.room, {"property": None, "capacity": 0, "occupied_beds": 0}
		)
		frappe.db.set_value("Tenant Space Allotment", allotment.name, {"property": None, "bed_no": 0})
		add_buildings_and_beds.execute()

		room = frappe.get_doc("Tenant Space", allotment.room)
		self.assertTrue(room.property)
		self.assertEqual((room.capacity, room.occupied_beds, room.status), (1, 1, "Occupied"))
		self.assertEqual(
			frappe.db.get_value("Tenant Space Allotment", allotment.name, ["property", "bed_no"]),
			(room.property, 1),
		)

	def test_room_defaults_to_a_building(self):
		room = make_room()
		self.assertTrue(room.property)


class IntegrationTestRentManagerRole(IntegrationTestCase):
	def test_rent_manager_permissions(self):
		email = "rent.manager@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": "Rent", "send_welcome_email": 0}
			).insert()
		user = frappe.get_doc("User", email)
		user.add_roles("Rent Manager")

		for doctype in (
			"Tenant",
			"Tenant Space",
			"Tenant Space Allotment",
			"Tenant Rent Invoice",
			"Rent Payment",
			"Security Deposit Settlement",
		):
			self.assertTrue(frappe.has_permission(doctype, "create", user=email), doctype)
		for doctype in ("Tenant Space Allotment", "Tenant Rent Invoice", "Rent Payment"):
			self.assertTrue(frappe.has_permission(doctype, "submit", user=email), doctype)
		self.assertTrue(frappe.has_permission("Rent Management Settings", "write", user=email))
