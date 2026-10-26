# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RentSubscriptionPayment(Document):
	def validate(self):
		# a paid record is what extended the subscription, so only the server may change it
		if (
			not self.is_new()
			and not frappe.flags.updating_rent_subscription
			and frappe.session.user != "Administrator"
		):
			frappe.throw(_("Subscription payments can't be edited."), frappe.PermissionError)

	def on_trash(self):
		if self.status == "Paid" and frappe.session.user != "Administrator":
			frappe.throw(_("Paid subscription payments can't be deleted."), frappe.PermissionError)
