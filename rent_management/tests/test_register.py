# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import random

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, get_datetime, nowdate

from rent_management import api, mess, portal, register
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


class TestRegister(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = frappe.get_doc(
			{
				"doctype": "Rent Property",
				"property_name": f"Hostel {frappe.generate_hash(length=4)}",
				"food_included": 1,
				"serves_breakfast": 1,
				"serves_lunch": 0,
				"serves_dinner": 1,
				"visitors_until": "21:00:00",
			}
		).insert()
		room = make_room(rent=6000, capacity=3, property=self.building.name)
		email = f"meera.{frappe.generate_hash(length=5)}@tenant.example"
		self.tenant = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": "Meera",
				"email_id": email,
				"mobile_no": f"98{random.randint(10**7, 10**8 - 1)}",
				"emergency_contact_name": "Lata",
				"emergency_contact_relation": "Mother",
				"emergency_contact_phone": "9845000222",
			}
		).insert()
		self.stay = make_allotment(room=room, tenant=self.tenant, allotment_date=add_days(nowdate(), -30))
		self.other = make_allotment(room=room, allotment_date=add_days(nowdate(), -30))
		api.invite_tenant(self.tenant.name)
		self.user = frappe.db.get_value("Tenant", self.tenant.name, "user")

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_tenant(self, method, *args, **kwargs):
		frappe.set_user(self.user)
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def test_leave_request_approval_skips_meals(self):
		start, end = add_days(nowdate(), 1), add_days(nowdate(), 3)
		data = self.as_tenant(portal.request_leave, start, end, destination="Mysuru")
		self.assertEqual(data["leaves"][0]["status"], "Requested")
		name = data["leaves"][0]["name"]
		self.assertTrue(frappe.db.exists("Notification Log", {"subject": ("like", "%asked for leave%")}))
		self.assertEqual(api.get_register(self.building.name)["leaves"]["requested"][0]["name"], name)
		# overlapping leave isn't allowed
		self.assertRaises(frappe.ValidationError, self.as_tenant, portal.request_leave, end, add_days(end, 2))

		api.decide_leave(name, 1)
		optouts = frappe.get_all(mess.OPTOUT, filters={"leave": name}, fields=["date", "meal", "source"])
		self.assertEqual(len(optouts), 6)  # 3 days x breakfast and dinner
		self.assertEqual({o.source for o in optouts}, {"Leave"})
		eating = {m["meal"]: m["eating"] for m in mess.kitchen_count(self.building.name, start)}
		self.assertEqual(eating, {"Breakfast": 1, "Dinner": 1})

		api.decide_leave(name, 0, note="Exams that week")
		self.assertFalse(frappe.db.exists(mess.OPTOUT, {"leave": name}))
		api.decide_leave(name, 1)
		self.as_tenant(portal.cancel_leave, name)
		self.assertEqual(frappe.db.get_value(register.LEAVE, name, "status"), "Cancelled")
		self.assertFalse(frappe.db.exists(mess.OPTOUT, {"leave": name}))

	def test_tenant_cant_touch_others_leave(self):
		name = api.add_leave(self.other.name, nowdate(), add_days(nowdate(), 1))
		self.assertEqual(frappe.db.get_value(register.LEAVE, name, "status"), "Approved")  # manager's
		self.assertRaises(frappe.PermissionError, self.as_tenant, portal.cancel_leave, name)
		self.assertRaises(
			frappe.ValidationError, api.add_leave, self.other.name, add_days(nowdate(), 2), nowdate()
		)

	def test_night_attendance(self):
		api.add_leave(self.other.name, nowdate(), add_days(nowdate(), 2))
		night = register.get_attendance(self.building.name)
		rows = {r["allotment"]: r for r in night["rows"]}
		self.assertEqual(rows[self.other.name]["status"], "On Leave")
		self.assertIsNone(rows[self.stay.name]["status"])
		self.assertEqual(rows[self.stay.name]["emergency"]["relation"], "Mother")

		entries = [
			{"allotment": self.stay.name, "status": "Absent", "note": "Not answering"},
			{"allotment": self.other.name, "status": "On Leave"},
		]
		name = api.save_attendance(self.building.name, nowdate(), entries)
		doc = frappe.get_doc(register.ATTENDANCE, name)
		self.assertEqual((doc.present, doc.absent, doc.on_leave), (0, 1, 1))
		# saving again updates the same night
		entries[0]["status"] = "Late"
		self.assertEqual(api.save_attendance(self.building.name, nowdate(), entries), name)
		night = register.get_attendance(self.building.name)
		self.assertTrue(night["taken"])
		self.assertEqual(night["history"][0]["late"], 1)
		self.assertRaises(
			frappe.ValidationError, api.save_attendance, self.building.name, add_days(nowdate(), 1), entries
		)

	def test_visitors(self):
		data = self.as_tenant(portal.expect_visitor, "Ramesh", nowdate(), purpose="Father", overnight=1)
		expected = data["visitors"][0]
		self.assertEqual((expected["status"], expected["overnight"]), ("Expected", 1))
		self.assertRaises(
			frappe.ValidationError, self.as_tenant, portal.expect_visitor, "Ramesh", add_days(nowdate(), -1)
		)
		visitors = register.get_visitors(self.building.name)
		self.assertEqual(visitors["expected"][0]["tenant_name"], self.tenant.full_name)

		api.visitor_in({"name": expected["name"]})
		walk_in = api.visitor_in({"visitor_name": "Plumber", "tenant": self.other.tenant, "purpose": "Tap"})
		self.assertEqual(frappe.db.get_value(register.VISITOR, walk_in, "property"), self.building.name)
		self.assertEqual(len(register.get_visitors(self.building.name)["inside"]), 2)
		api.visitor_out(walk_in)
		self.assertEqual(frappe.db.get_value(register.VISITOR, walk_in, "status"), "Left")

		late = frappe._dict(property=self.building.name, overnight=0)
		late.check_in = get_datetime(f"{nowdate()} 22:15:00")
		self.assertTrue(register.after_hours(late))
		late.overnight = 1
		self.assertFalse(register.after_hours(late))
		late.check_in = add_to_date(get_datetime(f"{nowdate()} 21:00:00"), minutes=-30)
		late.overnight = 0
		self.assertFalse(register.after_hours(late))
