# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class NightAttendance(Document):
	def validate(self):
		if frappe.db.exists(
			"Night Attendance", {"property": self.property, "date": self.date, "name": ("!=", self.name)}
		):
			frappe.throw(_("Attendance for {0} on {1} is already taken.").format(self.property, self.date))
		if not self.taken_by:
			self.taken_by = frappe.session.user
		counts = {"Present": 0, "Late": 0, "Absent": 0, "On Leave": 0}
		for row in self.entries:
			if row.status in counts:
				counts[row.status] += 1
		self.present, self.late, self.absent, self.on_leave = (
			counts["Present"],
			counts["Late"],
			counts["Absent"],
			counts["On Leave"],
		)
