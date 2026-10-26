# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import base64
import random
from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.xlsxutils import make_xlsx

from rent_management import api, data_import
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_property,
)


def csv_content(rows) -> str:
	text = "\n".join(",".join(str(c) for c in row) for row in rows)
	return base64.b64encode(text.encode()).decode()


def xlsx_content(rows) -> str:
	return base64.b64encode(make_xlsx(rows, "Sheet1").getvalue()).decode()


class TestDataImport(IntegrationTestCase):
	def setUp(self):
		self.building = make_property()
		self.suffix = frappe.generate_hash(length=4)

	def test_rooms_preview_then_import(self):
		rows = [
			["Building", "Room No", "Floor", "Sharing", "Type", "Rent", "Deposit"],
			[self.building, f"A{self.suffix}", "Ground", 2, f"Double {self.suffix}", 6000, 6000],
			[self.building, f"B{self.suffix}", "1", "", "", 4000, ""],
			[self.building, f"A{self.suffix}", "Ground", 2, "", "", ""],  # duplicate of row 2
			["", "", "", "", "", "", ""],  # blank rows are skipped
		]
		preview = api.import_data("rooms", "rooms.csv", csv_content(rows), dry_run=1)
		self.assertEqual((preview["ok"], preview["errors"]), (2, 1))
		self.assertIn("already exists", preview["rows"][2]["message"])
		# nothing was created by the preview
		self.assertFalse(frappe.db.exists("Tenant Space", {"room_number": f"A{self.suffix}"}))

		result = api.import_data("rooms", "rooms.csv", csv_content(rows), dry_run=0)
		self.assertEqual(result["ok"], 2)
		room = frappe.get_doc("Tenant Space", {"room_number": f"A{self.suffix}"})
		self.assertEqual(
			(room.property, room.capacity, room.room_type), (self.building, 2, f"Double {self.suffix}")
		)
		self.assertEqual(frappe.db.get_value("Tenant Space Type", room.room_type, "standard_rent"), 6000)
		self.assertEqual(
			frappe.db.get_value("Tenant Space", {"room_number": f"B{self.suffix}"}, "room_rent"), 4000
		)

	def test_tenants_with_rooms_from_excel(self):
		api.import_data(
			"rooms",
			"rooms.csv",
			csv_content(
				[
					["Building", "Room Number", "Beds", "Monthly Rent"],
					[self.building, f"T{self.suffix}", 2, 5000],
				]
			),
			dry_run=0,
		)
		mobile = "+91 9" + "".join(random.choices("0123456789", k=9))
		rows = [
			list(data_import.COLUMNS["tenants"]),
			[
				"Ravi Kumar",
				"",
				mobile,
				"",
				"m",
				"",
				"",
				self.building,
				f"T{self.suffix}",
				"",
				"05/09/2026",
				"",
				5000,
				"yes",
			],
			[
				"Asha",
				"Iyer",
				"",
				"",
				"F",
				"",
				"",
				"",
				f"T{self.suffix}",
				2,
				datetime(2026, 9, 10),
				4800,
				"",
				"",
			],
			[
				"Third",
				"Person",
				"",
				"",
				"",
				"",
				"",
				"",
				f"T{self.suffix}",
				"",
				"",
				"",
				"",
				"",
			],  # room is full now
			["", "No first name", "", "", "", "", "", "", "", "", "", "", "", ""],
		]
		preview = api.import_data("tenants", "tenants.xlsx", xlsx_content(rows), dry_run=1)
		# the preview applies rows in order, so it sees the room filling up
		self.assertEqual([r["status"] for r in preview["rows"]], ["ok", "ok", "error", "error"])
		self.assertIn("full", preview["rows"][2]["message"])

		api.import_data("tenants", "tenants.xlsx", xlsx_content(rows), dry_run=0)
		ravi = frappe.get_doc("Tenant", {"mobile_no": mobile})
		self.assertEqual((ravi.first_name, ravi.last_name, ravi.gender), ("Ravi", "Kumar", "Male"))
		allotment = frappe.get_doc("Tenant Space Allotment", {"tenant": ravi.name, "docstatus": 1})
		self.assertEqual(str(allotment.allotment_date), "2026-09-05")  # day first
		self.assertEqual(
			(allotment.bed_no, allotment.deposit_collected, allotment.security_deposit), (1, 1, 5000)
		)
		asha = frappe.get_doc("Tenant Space Allotment", {"tenant_name": "Asha Iyer", "docstatus": 1})
		self.assertEqual((asha.bed_no, asha.rent_amount), (2, 4800))

		# importing again matches tenants by mobile number instead of duplicating them
		again = api.import_data("tenants", "tenants.xlsx", xlsx_content(rows[:2]), dry_run=1)
		self.assertIn("Existing tenant", again["rows"][0]["message"])

	def test_bad_files(self):
		self.assertRaises(frappe.ValidationError, api.import_data, "rooms", "rooms.pdf", csv_content([["x"]]))
		self.assertRaises(
			frappe.ValidationError,
			api.import_data,
			"rooms",
			"rooms.csv",
			csv_content([["Colour", "Size"], [1, 2]]),
		)
		self.assertRaises(frappe.ValidationError, api.import_data, "cars", "x.csv", csv_content([["a"]]))

	def test_template(self):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		rows = read_xlsx_file_from_attached_file(fcontent=data_import.get_template("tenants"))
		self.assertEqual(rows[0][:3], ["First Name", "Last Name", "Mobile"])
