# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class MaintenanceRequest(Document):
	def validate(self):
		if self.status in ("Resolved", "Closed") and not self.resolved_on:
			self.resolved_on = now_datetime()
		elif self.status in ("Open", "In Progress"):
			self.resolved_on = None
		if self.tenant and not self.room:
			self.room = frappe.db.get_value(
				"Tenant Space Allotment", {"tenant": self.tenant, "docstatus": 1, "status": "Active"}, "room"
			)

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.status != self.status and self.raised_via == "Tenant App":
			frappe.enqueue(
				"rent_management.notifications.send_request_update",
				request=self.name,
				enqueue_after_commit=True,
				now=frappe.flags.in_test,
			)
