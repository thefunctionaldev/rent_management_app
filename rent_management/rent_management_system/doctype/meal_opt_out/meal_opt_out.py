# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MealOptout(Document):
	def validate(self):
		if frappe.db.exists(
			"Meal Opt-out",
			{"allotment": self.allotment, "date": self.date, "meal": self.meal, "name": ("!=", self.name)},
		):
			frappe.throw(_("{0} is already skipped on {1}.").format(self.meal, self.date))
