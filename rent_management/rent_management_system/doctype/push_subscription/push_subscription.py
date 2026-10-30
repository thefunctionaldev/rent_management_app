# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import hashlib

from frappe.model.document import Document


class PushSubscription(Document):
	def validate(self):
		self.endpoint_hash = hashlib.sha256((self.endpoint or "").encode()).hexdigest()
