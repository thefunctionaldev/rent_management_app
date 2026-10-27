# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""The public listing page: /stay (all buildings) and /stay/<building>.

The page itself is a small Vue app (frontend/src/stay); this only fills in the title and the
preview shown when the link is shared on WhatsApp."""

import frappe
from frappe.utils import escape_html, get_url, strip_html

from rent_management import leads

no_cache = 1


def get_context(context):
	if not leads.listing_enabled():
		raise frappe.PageDoesNotExistError
	slug = (frappe.form_dict.building or "").strip("/")
	if slug:
		try:
			doc = leads.get_building(slug)
		except frappe.DoesNotExistError:
			raise frappe.PageDoesNotExistError from None
		area = ", ".join(filter(None, [doc.city, doc.state]))
		title = f"{doc.property_name}{f' · {area}' if area else ''}"
		description = (
			doc.description or f"Rooms and beds at {doc.property_name}. Book a visit or hold a bed online."
		)
		image = doc.image
		url = get_url(f"/stay/{slug}")
	else:
		buildings = [frappe.get_doc("Rent Property", name) for name in leads.listed_buildings()]
		settings = frappe.get_single("Rent Management Settings")
		brand = (
			settings.upi_payee_name
			or settings.landlord_name
			or (buildings[0].property_name if buildings else "")
		)
		title = f"{brand} · Rooms and beds" if brand else "Rooms and beds"
		description = ", ".join(b.property_name for b in buildings) or title
		image = next((b.image for b in buildings if b.image), None)
		url = get_url("/stay")

	context.meta_title = escape_html(title)
	context.meta_description = escape_html(strip_html(description)[:300])
	context.meta_image = escape_html(get_url(image)) if image else ""
	context.meta_url = escape_html(url)
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.no_cache = 1
	return context
