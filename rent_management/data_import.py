# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Import rooms and tenants from the spreadsheets landlords already keep.

The upload is checked row by row first (every row is created and rolled back, so all the
normal validations and plan limits apply), then imported. Each row stands alone: a bad row
is reported and skipped, the others are imported.
"""

import base64
import csv
import io
import re
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from rent_management.rent_management_system.doctype.rent_property.rent_property import get_default_property

MAX_ROWS = 2000

# column label -> (field, other spellings people use)
COLUMNS = {
	"rooms": {
		"Building": ("property", ("property", "pg", "hostel", "building name")),
		"Room Number": ("room_number", ("room", "room no", "room no.", "room #")),
		"Floor": ("floor", ()),
		"Beds": ("capacity", ("bed", "beds", "sharing", "capacity", "no of beds")),
		"Room Type": ("room_type", ("type",)),
		"Monthly Rent": ("rent", ("rent", "rent per bed", "monthly rent per bed")),
		"Security Deposit": ("deposit", ("deposit",)),
	},
	"tenants": {
		"First Name": ("first_name", ("name", "tenant name", "full name", "tenant")),
		"Last Name": ("last_name", ("surname",)),
		"Mobile": ("mobile_no", ("phone", "mobile no", "mobile number", "contact", "whatsapp")),
		"Email": ("email_id", ("email id", "e-mail")),
		"Gender": ("gender", ()),
		"Occupation": ("occupation", ("job", "profession")),
		"Address": ("permanent_address", ("permanent address", "home address")),
		"Building": ("property", ("property", "pg", "hostel")),
		"Room Number": ("room", ("room", "room no", "room no.")),
		"Bed": ("bed_no", ("bed no", "bed number")),
		"Move-in Date": (
			"allotment_date",
			("move in date", "joining date", "check-in date", "checkin date", "from"),
		),
		"Monthly Rent": ("rent_amount", ("rent",)),
		"Security Deposit": ("security_deposit", ("deposit",)),
		"Deposit Collected": ("deposit_collected", ("deposit paid", "deposit received")),
	},
}

EXAMPLES = {
	"rooms": [
		["Main Building", "101", "Ground", 3, "Triple Sharing", 5000, 5000],
		["Main Building", "102", "Ground", 1, "Single AC", 11000, 11000],
	],
	"tenants": [
		[
			"Ravi",
			"Kumar",
			"+91 98765 43210",
			"ravi@example.com",
			"Male",
			"Engineer",
			"",
			"Main Building",
			"101",
			1,
			"01-09-2026",
			5000,
			5000,
			"Yes",
		],
		["Asha", "Iyer", "+91 91234 56780", "", "Female", "Student", "", "", "", "", "", "", "", ""],
	],
}


def get_template(kind: str) -> bytes:
	from frappe.utils.xlsxutils import make_xlsx

	columns = get_columns(kind)
	return make_xlsx([list(columns), *EXAMPLES[kind]], f"{kind.title()} import").getvalue()


def get_columns(kind: str) -> dict:
	if kind not in COLUMNS:
		frappe.throw(_("Choose rooms or tenants to import."))
	return COLUMNS[kind]


def normalise(label) -> str:
	return re.sub(r"\s+", " ", str(label or "").strip().lower().replace("_", " "))


def read_rows(kind: str, filename: str, content: str) -> list[dict]:
	"""Parse a base64 encoded .xlsx or .csv upload into dicts keyed by field."""
	data = base64.b64decode(content.split(",", 1)[-1])
	if filename.lower().endswith((".xlsx", ".xlsm")):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		rows = read_xlsx_file_from_attached_file(fcontent=data, read_only=True)
	elif filename.lower().endswith(".csv"):
		rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
	else:
		frappe.throw(_("Upload an Excel (.xlsx) or CSV file."))

	rows = [row for row in rows if any(str(cell or "").strip() for cell in row)]
	if not rows:
		frappe.throw(_("The file is empty."))
	if len(rows) - 1 > MAX_ROWS:
		frappe.throw(_("Import at most {0} rows at a time.").format(MAX_ROWS))

	lookup = {}
	for label, (field, aliases) in get_columns(kind).items():
		for spelling in (label, field, *aliases):
			lookup.setdefault(normalise(spelling), field)
	header = [lookup.get(normalise(cell)) for cell in rows[0]]
	required = "room_number" if kind == "rooms" else "first_name"
	if required not in header:
		frappe.throw(
			_(
				"Couldn't find the {0} column. Use the template, or name the first row's columns like it."
			).format(_("Room Number") if kind == "rooms" else _("First Name"))
		)

	parsed = []
	for number, row in enumerate(rows[1:], start=2):
		values = {"row": number}
		for field, cell in zip(header, row, strict=False):
			if field and cell not in (None, ""):
				values[field] = cell.strip() if isinstance(cell, str) else cell
		parsed.append(values)
	return parsed


def parse_date(value):
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	text = str(value).strip()
	match = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$", text)
	if match:  # Indian order: day first
		day, month, year = (int(g) for g in match.groups())
		return date(year + 2000 if year < 100 else year, month, day)
	return getdate(text)


def is_yes(value) -> bool:
	return normalise(value) in ("yes", "y", "1", "true", "paid", "collected", "done")


def run(kind: str, filename: str, content: str, dry_run: bool = True) -> dict:
	"""Import the rows, or with dry_run check them: rows are applied in order inside one
	transaction that is rolled back, so the preview sees what earlier rows would create."""
	rows = read_rows(kind, filename, content)
	importer = import_room if kind == "rooms" else import_tenant
	results = []
	frappe.db.savepoint("rent_import")
	for row in rows:
		frappe.db.savepoint("rent_import_row")
		try:
			message = importer(frappe._dict(row))
			status = "ok"
		except Exception as e:
			frappe.db.rollback(save_point="rent_import_row")
			status, message = "error", strip_html(str(e)) or _("Could not import this row")
		results.append({"row": row["row"], "status": status, "message": message, "values": serialise(row)})
	if dry_run:
		frappe.db.rollback(save_point="rent_import")
	frappe.clear_messages()  # per-row alerts ("moved into room...") are in the results already

	ok = sum(1 for r in results if r["status"] == "ok")
	return {"rows": results, "ok": ok, "errors": len(results) - ok, "dry_run": dry_run}


def strip_html(text: str) -> str:
	return re.sub(r"<[^>]+>", "", text).strip()


def serialise(row: dict) -> dict:
	return {k: (v.isoformat() if isinstance(v, date | datetime) else v) for k, v in row.items() if k != "row"}


# ---------------------------------------------------------------- rooms


def get_property(name) -> str:
	if not name:
		return get_default_property()
	existing = frappe.db.get_value("Rent Property", {"property_name": name}) or frappe.db.get_value(
		"Rent Property", {"abbr": str(name).upper()}
	)
	if existing:
		return existing
	return frappe.get_doc({"doctype": "Rent Property", "property_name": name}).insert().name


def get_room_type(name, rent, deposit) -> str | None:
	if not name:
		return None
	if frappe.db.exists("Tenant Space Type", name):
		return name
	return (
		frappe.get_doc(
			{
				"doctype": "Tenant Space Type",
				"type": name,
				"standard_rent": flt(rent),
				"deposit_applicable": 1 if flt(deposit) else 0,
				"security_deposit": flt(deposit),
			}
		)
		.insert()
		.name
	)


def import_room(row) -> str:
	if not row.room_number:
		frappe.throw(_("Room Number is missing."))
	room = frappe.get_doc(
		{
			"doctype": "Tenant Space",
			"property": get_property(row.property),
			"room_number": str(row.room_number).removesuffix(".0"),
			"floor": str(row.floor).removesuffix(".0") if row.floor is not None else None,
			"capacity": cint(row.capacity) or 1,
			"room_type": get_room_type(row.room_type, row.rent, row.deposit),
			"room_rent": flt(row.rent) or None,
		}
	).insert()
	return _("Room {0} in {1}, {2} bed(s)").format(room.room_number, room.property, room.capacity)


# ---------------------------------------------------------------- tenants


def find_room(room_number, property_name) -> str:
	room_number = str(room_number).removesuffix(".0")
	filters = {"room_number": room_number}
	if property_name:
		filters["property"] = get_existing_property(property_name)
	rooms = frappe.get_all("Tenant Space", filters=filters, pluck="name")
	if not rooms:
		frappe.throw(_("Room {0} not found. Import rooms first.").format(room_number))
	if len(rooms) > 1:
		frappe.throw(
			_("Room {0} exists in several buildings. Fill in the Building column.").format(room_number)
		)
	return rooms[0]


def get_existing_property(name) -> str:
	existing = frappe.db.get_value("Rent Property", {"property_name": name}) or frappe.db.get_value(
		"Rent Property", {"abbr": str(name).upper()}
	)
	if not existing:
		frappe.throw(_("Building {0} not found.").format(name))
	return existing


def split_name(row):
	if row.first_name and not row.last_name and " " in str(row.first_name).strip():
		first, _sep, last = str(row.first_name).strip().partition(" ")
		return first, last
	return row.first_name, row.last_name


def import_tenant(row) -> str:
	first_name, last_name = split_name(row)
	if not first_name:
		frappe.throw(_("First Name is missing."))
	mobile = str(row.mobile_no).removesuffix(".0") if row.mobile_no else None

	existing = frappe.db.get_value("Tenant", {"mobile_no": mobile}) if mobile else None
	if existing:
		tenant = frappe.get_doc("Tenant", existing)
		message = _("Existing tenant {0}").format(tenant.full_name)
	else:
		gender = str(row.gender or "").strip().title()
		tenant = frappe.get_doc(
			{
				"doctype": "Tenant",
				"first_name": first_name,
				"last_name": last_name,
				"mobile_no": mobile,
				"email_id": row.email_id,
				"gender": {"M": "Male", "F": "Female"}.get(gender, gender) or None,
				"occupation": row.occupation,
				"permanent_address": row.permanent_address,
			}
		).insert()
		message = _("New tenant {0}").format(tenant.full_name)

	if not row.room:
		return message
	if existing:
		current = frappe.db.get_value(
			"Tenant Space Allotment", {"tenant": tenant.name, "docstatus": 1, "status": "Active"}, "room"
		)
		if current:
			return _("{0}, already staying in room {1}").format(message, current)

	allotment_date = parse_date(row.allotment_date) if row.allotment_date else getdate(nowdate())
	deposit_collected = is_yes(row.deposit_collected)
	allotment = frappe.get_doc(
		{
			"doctype": "Tenant Space Allotment",
			"tenant": tenant.name,
			"room": find_room(row.room, row.property),
			"bed_no": cint(row.bed_no) or None,
			"allotment_date": allotment_date,
			"rent_amount": flt(row.rent_amount) or None,
			"security_deposit": flt(row.security_deposit) or None,
			"deposit_collected": 1 if deposit_collected else 0,
			"deposit_collected_on": allotment_date if deposit_collected else None,
		}
	).insert()
	allotment.submit()
	return _("{0}, moved into room {1} bed {2} on {3}").format(
		message, allotment.room, allotment.bed_no, frappe.utils.formatdate(allotment_date)
	)
