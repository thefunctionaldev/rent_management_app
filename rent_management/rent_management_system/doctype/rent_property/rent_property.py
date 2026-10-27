# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


class RentProperty(Document):
	def validate(self):
		self.abbr = (self.abbr or "").strip().upper()
		if not self.abbr:
			self.abbr = make_abbr(self.property_name)
		if not self.listing_slug:
			self.listing_slug = make_slug(self.property_name, self.name)


def make_slug(name: str, current=None) -> str:
	"""The building's address on the listing page: Sunrise PG -> /stay/sunrise-pg"""
	slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:60] or "building"
	candidate, n = slug, 1
	while frappe.db.exists("Rent Property", {"listing_slug": candidate, "name": ("!=", current or "")}):
		n += 1
		candidate = f"{slug}-{n}"
	return candidate


def make_abbr(name: str) -> str:
	words = [w for w in (name or "").replace("-", " ").split() if w[0].isalnum()]
	abbr = "".join(w[0] for w in words).upper()[:6] or "B"
	candidate, n = abbr, 1
	while frappe.db.exists("Rent Property", {"abbr": candidate}):
		n += 1
		candidate = f"{abbr}{n}"
	return candidate


def get_default_property() -> str:
	"""The building new rooms go into when none is given: the only one, or a new "Main Building"."""
	properties = frappe.get_all(
		"Rent Property", filters={"is_active": 1}, pluck="name", order_by="creation asc"
	)
	if properties:
		return properties[0]
	return (
		frappe.get_doc({"doctype": "Rent Property", "property_name": "Main Building", "abbr": "MAIN"})
		.insert(ignore_permissions=True)
		.name
	)
