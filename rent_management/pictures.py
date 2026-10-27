# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Photos of tenants and buildings.

The browser sends the picture as a data URL (it shrinks it first). Tenant photos are private
files: only managers (and the tenant, through the tenant app) can see them. Building photos
are public, like a listing photo.
"""

import base64
import binascii
import io
import re

import frappe
from frappe import _
from frappe.utils import random_string

MAX_BYTES = 5 * 1024 * 1024
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
FIELDS = {
	# doctype: (field, private)
	"Tenant": ("display_picture", True),
	"Rent Property": ("image", False),
}
DATA_URL = re.compile(r"^data:image/[a-z+]+;base64,(?P<data>.+)$", re.S)


def set_picture(doc, picture: str | None):
	"""Replace the photo of a Tenant or Rent Property with a data URL, or remove it ("")."""
	if picture is None:
		return  # not changed
	field, private = FIELDS[doc.doctype]
	old = doc.get(field)
	url = save_file(doc, field, private, picture) if picture else None
	doc.db_set(field, url)
	if old and old != url:
		delete_file(doc, old)


def save_file(doc, field, private, picture) -> str:
	content, extension = decode(picture)
	slug = re.sub(r"[^a-z0-9]+", "-", str(doc.get("full_name") or doc.name).lower()).strip("-")
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{slug or 'photo'}-{random_string(6).lower()}.{extension}",
			"content": content,
			"is_private": 1 if private else 0,
			"attached_to_doctype": doc.doctype,
			"attached_to_name": str(doc.name),
			"attached_to_field": field,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	return file.file_url


def decode(picture: str) -> tuple[bytes, str]:
	"""The bytes and file extension of a data URL, if it really is a JPEG, PNG or WebP image."""
	from PIL import Image

	match = DATA_URL.match(picture or "")
	if not match:
		frappe.throw(_("Please choose a JPEG, PNG or WebP picture."))
	try:
		content = base64.b64decode(match.group("data"), validate=True)
	except binascii.Error, ValueError:
		frappe.throw(_("The picture could not be read. Please choose it again."))
	if len(content) > MAX_BYTES:
		frappe.throw(_("The picture is too large (5 MB at most)."))
	try:
		with Image.open(io.BytesIO(content)) as image:
			image_format = image.format
			image.verify()
	except Exception:
		image_format = None
	if image_format not in FORMATS:
		frappe.throw(_("Please choose a JPEG, PNG or WebP picture."))
	return content, FORMATS[image_format]


def delete_file(doc, url):
	for name in frappe.get_all(
		"File",
		filters={"file_url": url, "attached_to_doctype": doc.doctype, "attached_to_name": str(doc.name)},
		pluck="name",
	):
		frappe.delete_doc("File", name, ignore_permissions=True)


def tenant_pictures(tenants) -> dict:
	"""{tenant: photo URL} for showing photos next to names in lists."""
	names = {str(t) for t in tenants if t}
	if not names:
		return {}
	return {
		str(t.name): t.display_picture
		for t in frappe.get_all(
			"Tenant",
			filters={"name": ("in", list(names)), "display_picture": ("is", "set")},
			fields=["name", "display_picture"],
		)
	}


def add_tenant_pictures(rows, key="tenant"):
	pictures = tenant_pictures(row.get(key) for row in rows)
	for row in rows:
		row["tenant_picture"] = pictures.get(str(row.get(key)))
	return rows
