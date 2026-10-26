# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RentSubscription(Document):
	def validate(self):
		# role permissions only allow reading, this also stops a customer who was given write
		# access (e.g. via Role Permissions Manager) from extending their own subscription
		if not (frappe.flags.updating_rent_subscription or frappe.session.user == "Administrator"):
			frappe.throw(_("The subscription changes only when a plan is paid for."), frappe.PermissionError)
