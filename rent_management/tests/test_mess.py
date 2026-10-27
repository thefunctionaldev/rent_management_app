# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_first_day, getdate, now_datetime, nowdate

from rent_management import api, mess, portal
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_portal import make_portal_tenant


class TestMess(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.building = frappe.get_doc(
			{
				"doctype": "Rent Property",
				"property_name": f"Mess Villa {frappe.generate_hash(length=4)}",
				"food_included": 1,
				"serves_lunch": 0,
				"breakfast_time": "08:00:00",
				"dinner_time": "20:30:00",
				"meal_skip_cutoff_hours": 4,
			}
		).insert()
		self.room = make_room(rent=8000, capacity=3, property=self.building.name)
		self.stays = [
			make_allotment(room=self.room, allotment_date=add_days(nowdate(), -20)) for _i in range(2)
		]

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_meal_plan_defaults_from_the_building(self):
		self.assertEqual([m["meal"] for m in mess.meals_of(self.building.name)], ["Breakfast", "Dinner"])
		self.assertEqual(self.stays[0].meal_plan, "Included in Rent")
		plain = make_allotment(room=make_room(rent=5000))
		self.assertFalse(plain.meal_plan)

	def test_kitchen_count_and_skipping(self):
		tomorrow = add_days(nowdate(), 1)
		api.skip_meal_for(self.stays[0].name, tomorrow, "Dinner")
		counts = {m["meal"]: m for m in mess.kitchen_count(self.building.name, tomorrow)}
		self.assertEqual((counts["Breakfast"]["eating"], counts["Dinner"]["eating"]), (2, 1))
		self.assertEqual(counts["Dinner"]["skipping"][0]["tenant_name"], self.stays[0].tenant_name)
		self.assertRaises(frappe.ValidationError, api.skip_meal_for, self.stays[0].name, tomorrow, "Lunch")
		api.skip_meal_for(self.stays[0].name, tomorrow, "Dinner", skip=0)
		self.assertEqual(mess.kitchen_count(self.building.name, tomorrow)[1]["eating"], 2)

	def test_tenant_skips_before_the_cutoff(self):
		tenant, stay, _invoice = make_portal_tenant("Rahul")
		stay = frappe.get_doc("Tenant Space Allotment", stay.name)
		api.set_meal_plan(stay.name, "Included in Rent")
		frappe.db.set_value("Tenant Space Allotment", stay.name, "property", self.building.name)
		frappe.set_user(tenant.user)
		self.assertTrue(portal.get_boot()["food"])
		day = add_days(nowdate(), 2)
		week = portal.skip_meal(day, "Breakfast")
		row = next(
			m for d in week["days"] if d["date"] == str(day) for m in d["meals"] if m["meal"] == "Breakfast"
		)
		self.assertFalse(row["eating"])
		# too late: 4 hours before breakfast has passed
		late = now_datetime() + timedelta(hours=1)
		with patch.object(
			mess, "now_datetime", return_value=late.replace(hour=7, minute=0) if late.hour < 23 else late
		):
			self.assertRaises(frappe.ValidationError, portal.skip_meal, getdate(late), "Breakfast")

	def test_paid_meal_plan_on_invoices(self):
		stay = make_allotment(room=self.room, allotment_date=get_first_day(nowdate()))
		api.set_meal_plan(stay.name, "Paid Monthly", 3000)
		from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import (
			MONTHS,
		)

		today = getdate(nowdate())
		invoice = make_invoice(stay, billing_month=MONTHS[today.month - 1], billing_year=today.year)
		food = [c for c in invoice.charges if c.charge_type == "Food"]
		self.assertEqual(len(food), 1)
		self.assertEqual(food[0].amount, 3000)
		api.set_meal_plan(self.stays[0].name, "Included in Rent", 3000)
		self.assertEqual(frappe.db.get_value("Tenant Space Allotment", self.stays[0].name, "meal_charge"), 0)

	def test_menu_and_costs(self):
		menu = mess.get_menu(self.building.name)
		menu["Monday"]["Breakfast"] = "Idli, sambar, chutney"
		api.save_menu(self.building.name, menu)
		self.assertEqual(mess.get_menu(self.building.name)["Monday"]["Breakfast"], "Idli, sambar, chutney")
		frappe.get_doc({"doctype": "Property Expense", "property": self.building.name, "expense_date": nowdate(),
			"category": "Food & Groceries", "amount": 6000}).insert()  # fmt: skip
		data = api.get_food(property=self.building.name)
		costs = data["buildings"][0]["costs"]
		self.assertEqual(costs["spent"], 6000)
		self.assertGreater(costs["meals_served"], 0)
		self.assertGreater(costs["per_meal"], 0)
