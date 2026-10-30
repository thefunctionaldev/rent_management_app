# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from rent_management import access, api, register, salaries
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_property,
	make_room,
)


class TestStaffAccess(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.a, self.b = make_property(), make_property()
		self.stay_a = make_allotment(
			room=make_room(rent=6000, property=self.a), allotment_date=add_days(nowdate(), -10)
		)
		self.stay_b = make_allotment(
			room=make_room(rent=6000, property=self.b), allotment_date=add_days(nowdate(), -10)
		)
		self.warden = self.staff_login("Manjunath", self.a, ["register", "payments"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.rent_staff_access = {}

	def staff_login(self, name, building, areas, all_buildings=0):
		staff = api.save_staff(
			{"staff_name": name, "role": "Warden", "property": building, "monthly_salary": 12000}
		)
		email = f"{name.lower()}.{frappe.generate_hash(length=5)}@staff.example"
		result = api.give_staff_login(staff, email, areas, all_buildings)
		self.assertIn("/update-password?key=", result["link"])
		return frappe._dict(staff=staff, user=email)

	def as_user(self, user):
		frappe.set_user(user)
		frappe.local.rent_staff_access = {}

	def test_the_login(self):
		user = frappe.get_doc("User", self.warden.user)
		self.assertEqual(user.user_type, "Website User")  # no Desk
		self.assertIn(access.STAFF_ROLE, frappe.get_roles(user.name))
		self.as_user(self.warden.user)
		boot = api.get_boot()
		self.assertEqual(
			boot["access"], {"areas": ["payments", "register"], "building": self.a, "staff_name": "Manjunath"}
		)
		self.assertEqual([p.name for p in boot["properties"]], [self.a])

		frappe.set_user("Administrator")
		api.remove_staff_login(self.warden.staff)
		self.assertEqual(frappe.db.get_value("User", self.warden.user, "enabled"), 0)
		self.assertNotIn(access.STAFF_ROLE, frappe.get_roles(self.warden.user))

	def test_only_their_areas(self):
		self.as_user(self.warden.user)
		self.assertTrue(api.get_register(self.a)["buildings"])
		for denied in (
			lambda: api.get_profit_and_loss(),
			lambda: api.get_salaries(),
			lambda: api.get_settings(),
			lambda: api.get_food(property=self.a),  # not one of their areas
			lambda: api.reveal_aadhaar(self.stay_a.tenant),
			lambda: api.get_dashboard(self.a),
			lambda: api.give_staff_login(self.warden.staff, self.warden.user, ["food"]),
		):
			self.assertRaises(frappe.PermissionError, denied)

	def test_only_their_building(self):
		self.as_user(self.warden.user)
		self.assertRaises(frappe.PermissionError, api.get_register, self.b)
		self.assertRaises(frappe.PermissionError, api.get_register)  # all buildings
		api.save_attendance(self.a, nowdate(), [{"allotment": self.stay_a.name, "status": "Present"}])

		# Frappe's own record APIs: their areas and building only
		self.assertEqual(
			{r.property for r in frappe.get_list(register.ATTENDANCE, fields=["property"])}, {self.a}
		)
		self.assertEqual(frappe.get_list("Property Expense"), [])  # not an area of theirs
		frappe.set_user("Administrator")
		night_b = register.save_attendance(
			self.b, nowdate(), [{"allotment": self.stay_b.name, "status": "Present"}]
		)
		self.as_user(self.warden.user)
		self.assertFalse(frappe.has_permission(register.ATTENDANCE, "read", doc=night_b))
		self.assertFalse(frappe.has_permission(salaries.SLIP, "read"))

	def test_staff_are_notified_for_their_building(self):
		register.request_leave(self.stay_a.name, nowdate(), add_days(nowdate(), 2))
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"for_user": self.warden.user, "link": "/rent/register?tab=leave"}
			)
		)
		frappe.db.delete("Notification Log", {"for_user": self.warden.user})
		register.request_leave(self.stay_b.name, nowdate(), add_days(nowdate(), 2))
		self.assertFalse(frappe.db.exists("Notification Log", {"for_user": self.warden.user}))

	def test_all_buildings_login(self):
		cook = self.staff_login("Lakshmamma", self.a, ["food"], all_buildings=1)
		self.as_user(cook.user)
		self.assertIsNone(api.get_boot()["access"]["building"])
		api.get_food()  # every building
		self.assertIn("food", api.get_staff_home(self.a))
		self.assertRaises(frappe.PermissionError, api.get_register, self.a)
