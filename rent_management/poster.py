# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""A printable A4 poster for a building's gate: its listing page as a QR code.

People walking past scan it to see the rooms, prices and photos, and book (leads.py). The
poster shows the building's name and photo, who it's for, the rent it starts from, a few
amenities, and the landlord's phone number (Settings).
"""

import base64
import io
import re

import frappe
from frappe import _
from frappe.utils import cint


def qr_svg(url: str) -> str:
	import pyqrcode

	out = io.BytesIO()
	pyqrcode.create(url, error="M").svg(out, scale=1, quiet_zone=4, xmldecl=False, svgns=True)
	svg = out.getvalue().decode()
	size = re.search(r'width="(\d+)"', svg).group(1)
	# a viewBox so it scales to the poster instead of being cut off
	return re.sub(
		r'height="\d+" width="\d+"', f'viewBox="0 0 {size} {size}" shape-rendering="crispEdges"', svg, count=1
	)


def image_data_url(path) -> str | None:
	"""The building's photo, inside the page (the PDF maker can't open private files)."""
	if not path:
		return None
	try:
		content = frappe.get_doc("File", {"file_url": path}).get_content(encodings=[])
	except Exception:
		return None
	kind = "png" if path.lower().endswith(".png") else "jpeg"
	return f"data:image/{kind};base64,{base64.b64encode(content).decode()}"


def context(property) -> frappe._dict:
	from rent_management import leads, receipts

	settings = frappe.get_cached_doc("Rent Management Settings")
	doc = frappe.get_doc("Rent Property", property)
	if not cint(settings.listing_enabled):
		frappe.throw(_("Turn on the listing page in Settings first: the poster links to it."))
	if not (doc.is_active and doc.show_on_listing):
		frappe.throw(
			_("Show {0} on the listing page first: the poster links to it.").format(doc.property_name)
		)
	card = leads.building_card(doc)
	url = leads.listing_url(doc.name)
	return frappe._dict(
		card=card,
		url=url,
		short_url=url.split("://", 1)[-1],
		qr=qr_svg(url),
		image=image_data_url(doc.image),
		amenities=card["amenities"][:6],
		phone=settings.landlord_phone,
		inr=receipts.inr,
	)


def html(property) -> str:
	return frappe.render_template("rent_management/templates/listing_poster.html", {"p": context(property)})


def send_pdf(property):
	from rent_management import pdf

	page = html(property)
	name = frappe.db.get_value("Rent Property", property, "property_name") or property
	frappe.local.response.filename = f"Poster-{name.replace(' ', '-')}.pdf"
	frappe.local.response.filecontent = pdf.of_html(page, {"page-size": "A4", "margin-top": "0", "margin-bottom": "0", "margin-left": "0", "margin-right": "0"})  # fmt: skip
	frappe.local.response.type = "pdf"
