# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from rent_management import api, inspections
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)
from rent_management.tests.test_pictures import data_url

ITEMS = [
	{"item": "Bed", "quantity": 1, "replacement_cost": 3000},
	{"item": "Chair", "quantity": 2, "replacement_cost": 1200},
	{"item": "Room key", "quantity": 1, "replacement_cost": 300},
]


class TestInspections(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		room = make_room(rent=6000, deposit=12000)
		api.save_room({"name": room.name, "items": ITEMS})
		self.room = room.name
		self.stay = make_allotment(room=frappe.get_doc("Tenant Space", room.name), allotment_date=nowdate(),
			security_deposit=12000, deposit_collected=1)  # fmt: skip

	def checklist(self, inspection_type):
		return api.get_room_inspection(self.stay.name, inspection_type)

	def test_room_items(self):
		items = api.get_room_items(self.room)
		self.assertEqual([i.item for i in items["items"]], ["Bed", "Chair", "Room key"])
		self.assertTrue(items["suggestions"])

	def test_move_in_then_move_out(self):
		move_in = self.checklist("Move-in")
		self.assertIsNone(move_in["name"])
		self.assertEqual((move_in["items"][0]["item"], move_in["items"][0]["condition"]), ("Bed", "Good"))
		move_in["items"][1]["condition"] = "Fair"
		move_in["items"][1]["notes"] = "Scratches on one"
		move_in["items"][0]["photo_upload"] = data_url()
		api.save_room_inspection({**move_in, "complete": 1})
		saved = inspections.existing(self.stay.name, "Move-in")
		self.assertEqual(saved.status, "Completed")
		self.assertTrue(saved.items[0].photo.startswith("/private/files/"))
		self.assertEqual(saved.total_charges, 0)  # nothing is charged at move-in

		# the agreement shows the room's condition
		from frappe.www.printview import get_rendered_template

		html = get_rendered_template(
			self.stay, print_format=frappe.get_doc("Print Format", api.AGREEMENT_FORMAT)
		)
		self.assertIn("Room Condition at Move-in", html)
		self.assertIn("Scratches on one", html)

		# move-out starts from the move-in condition
		move_out = self.checklist("Move-out")
		self.assertEqual([r["move_in_condition"] for r in move_out["items"]], ["Good", "Fair", "Good"])
		move_out["items"][0]["condition"] = "Damaged"
		move_out["items"][0]["charge"] = 1500
		move_out["items"][2]["condition"] = "Missing"  # charged at replacement cost
		api.save_room_inspection({**move_out, "complete": 1})
		self.assertEqual(inspections.existing(self.stay.name, "Move-out").total_charges, 1800)

		deductions = api.get_checklist_deductions(self.stay.name)["deductions"]
		self.assertEqual(
			[(d["reason"], d["amount"]) for d in deductions], [("Damages", 1500), ("Lost Keys", 300)]
		)
		self.assertIn("Bed: damaged", deductions[0]["description"])

		# settled with those deductions: the checklist is final
		api.vacate_room(self.stay.name, nowdate())
		api.settle_deposit(self.stay.name, deductions=deductions)
		self.assertTrue(inspections.is_locked(self.stay.name, "Move-out"))
		self.assertRaises(frappe.ValidationError, api.save_room_inspection, {**move_out, "complete": 1})

	def test_one_checklist_of_each_kind(self):
		api.save_room_inspection(self.checklist("Move-in"))
		duplicate = frappe.get_doc(
			{
				"doctype": "Room Inspection",
				"allotment": self.stay.name,
				"inspection_type": "Move-in",
				"inspection_date": nowdate(),
			}
		)
		self.assertRaises(frappe.ValidationError, duplicate.insert)

	def test_move_in_locked_once_signed(self):
		api.save_room_inspection({**self.checklist("Move-in"), "complete": 1})
		frappe.get_doc(
			{
				"doctype": "Tenant Check-in",
				"tenant": self.stay.tenant,
				"allotment": self.stay.name,
				"status": "Signed",
			}
		).insert()
		self.assertTrue(self.checklist("Move-in")["locked"])
		self.assertRaises(frappe.ValidationError, api.save_room_inspection, self.checklist("Move-in"))
