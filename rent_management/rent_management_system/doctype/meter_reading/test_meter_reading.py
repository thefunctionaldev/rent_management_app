# Copyright (c) 2026, Shashank Dixit and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from rent_management import api
from rent_management.rent_management_system.doctype.tenant_rent_invoice.test_tenant_rent_invoice import (
	make_invoice,
)
from rent_management.rent_management_system.doctype.tenant_space_allotment.test_tenant_space_allotment import (
	make_allotment,
	make_room,
)


def make_reading(room, date, reading, **kwargs):
	return frappe.get_doc(
		{"doctype": "Meter Reading", "room": room.name, "reading_date": date, "reading": reading, **kwargs}
	).insert()


class IntegrationTestMeterReading(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("Rent Management Settings", "electricity_rate", 10)
		self.room = make_room(capacity=2)
		self.room.has_meter = 1
		self.room.save()

	def test_units_split_by_days_and_billed_once(self):
		# A stays the whole of January, B moves in on the 17th (15 days)
		a = make_allotment(room=self.room, allotment_date="2025-12-01")
		b = make_allotment(room=self.room, allotment_date="2026-01-17")
		opening = make_reading(self.room, "2025-12-31", 1000)
		self.assertEqual((opening.status, opening.units, opening.shares), ("Opening", 0, []))

		reading = make_reading(self.room, "2026-01-31", 1092)
		self.assertEqual(
			(reading.units, reading.rate, reading.amount, reading.status), (92, 10, 920, "Unbilled")
		)
		shares = {s.tenant_space_allotment: s for s in reading.shares}
		self.assertEqual((shares[a.name].days, shares[b.name].days), (31, 15))
		self.assertEqual(shares[a.name].amount + shares[b.name].amount, 920)
		self.assertAlmostEqual(shares[a.name].units, 92 * 31 / 46, places=1)

		# the next invoice picks up the tenant's share
		invoice = make_invoice(a, billing_month="February", posting_date="2026-02-01", submit=True)
		electricity = [c for c in invoice.charges if c.charge_type == "Electricity"]
		self.assertEqual(len(electricity), 1)
		self.assertEqual(electricity[0].amount, shares[a.name].amount)
		self.assertEqual(invoice.final_amount, invoice.pro_rated_rent + shares[a.name].amount)
		reading.reload()
		self.assertEqual(reading.status, "Partly Billed")

		# and only once
		march = make_invoice(a, billing_month="March", posting_date="2026-03-01")
		self.assertFalse([c for c in march.charges if c.charge_type == "Electricity"])

		# a billed reading can't be changed; cancelling the invoice frees it again
		reading.reading = 1100
		self.assertRaises(frappe.ValidationError, reading.save)
		invoice.cancel()
		reading.reload()
		self.assertEqual(reading.status, "Unbilled")

	def test_empty_room_is_not_billed(self):
		make_reading(self.room, "2026-01-01", 50)
		reading = make_reading(self.room, "2026-01-31", 80)
		self.assertEqual((reading.units, reading.status, reading.shares), (30, "Not Billable", []))

	def test_reading_checks(self):
		make_reading(self.room, "2026-01-01", 500)
		self.assertRaises(frappe.ValidationError, make_reading, self.room, "2026-01-31", 400)  # went down
		self.assertRaises(frappe.ValidationError, make_reading, self.room, "2026-01-01", 600)  # same day
		replaced = make_reading(self.room, "2026-01-31", 40, meter_replaced=1)
		self.assertEqual(replaced.units, 40)
		self.assertRaises(frappe.ValidationError, make_reading, self.room, "2026-01-15", 520)  # out of order

		no_meter = make_room()
		self.assertRaises(frappe.ValidationError, make_reading, no_meter, "2026-01-01", 1)

	def test_room_rate_overrides_settings(self):
		self.room.electricity_rate = 8
		self.room.save()
		make_allotment(room=self.room, allotment_date="2025-12-01")
		make_reading(self.room, "2025-12-31", 0)
		self.assertEqual(make_reading(self.room, "2026-01-31", 100).amount, 800)

	def test_bulk_entry(self):
		allotment = make_allotment(room=self.room, allotment_date="2025-12-01")
		api.save_meter_readings("2025-12-31", [{"room": self.room.name, "reading": 10}])
		results = api.save_meter_readings(
			"2026-01-31", [{"room": self.room.name, "reading": 30}, {"room": "no-such-room", "reading": 5}]
		)
		self.assertEqual(results[0]["amount"], 200)
		self.assertIn("error", results[1])
		pending = {a.name: a.pending_electricity for a in api.get_billable_allotments()}
		self.assertEqual(pending[allotment.name], 200)
		rooms = {r.name: r for r in api.get_meter_rooms()["rooms"]}
		self.assertEqual(rooms[self.room.name].last_reading, 30)
