# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string


class RentLead(Document):
	def validate(self):
		self.lead_name = (self.lead_name or "").strip()
		self.mobile_no = re.sub(r"[^\d+]", "", self.mobile_no or "")
		if len(re.sub(r"\D", "", self.mobile_no)) < 10:
			frappe.throw(_("Please enter a valid mobile number."))
		if self.email_id:
			self.email_id = self.email_id.strip().lower()
		if not self.access_key:
			self.access_key = random_string(32)
		if self.room and frappe.db.get_value("Tenant Space", self.room, "property") != self.property:
			frappe.throw(_("Room {0} is not in {1}.").format(self.room, self.property))
		if self.status == "Booked" and not (self.room or self.room_type):
			frappe.throw(_("Choose the room or room type the bed is held in."))
		if self.status != "Lost":
			self.lost_reason = None
