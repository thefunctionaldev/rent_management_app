# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Rent receipts for income tax: what salaried tenants give their employer to claim HRA.

A receipt shows who paid rent to whom (with the landlord's PAN, which employers need when
the rent is over ₹1,00,000 a year), for which property and month, how much and how it was
paid. Only the rent counts, not electricity, food or late fees. Tenants download one for a
month or one for the whole financial year (April to March) from the tenant app; managers
from the tenant's page.

The payee is the building's owner when set (Rent Property: owner_name, owner_pan,
owner_address), else the landlord in Rent Management Settings.
"""

import base64
import re
from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from rent_management.rent_management_system.doctype.tenant_rent_invoice.tenant_rent_invoice import MONTHS

INVOICE = "Tenant Rent Invoice"
SETTINGS = "Rent Management Settings"
PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PAN_LIMIT = 100000  # employers need the landlord's PAN above this much rent a year
STAMP_LIMIT = 5000  # a cash receipt above this needs a revenue stamp


def check_pan(doc, method=None):
	"""Rent Management Settings / Rent Property validate: a PAN looks like ABCDE1234F."""
	for field in ("landlord_pan", "owner_pan"):
		if doc.meta.has_field(field) and doc.get(field):
			doc.set(field, doc.get(field).strip().upper())
			if not PAN.match(doc.get(field)):
				frappe.throw(_("{0} doesn't look like a PAN (like ABCDE1234F).").format(doc.get(field)))


# ---------------------------------------------------------------- financial years


def fy_start(day) -> date:
	"""The 1 April a financial year starts on, from a day in it or its label (2025-26)."""
	if isinstance(day, str) and re.match(r"^\d{4}-\d{2}$", day):
		return fy_from_label(day)
	day = getdate(day)
	return date(day.year if day.month >= 4 else day.year - 1, 4, 1)


def fy_label(start) -> str:
	return f"{start.year}-{str(start.year + 1)[-2:]}"


def fy_from_label(label) -> date:
	match = re.match(r"^(\d{4})-\d{2}$", str(label or ""))
	if not match:
		return fy_start(nowdate())
	return date(int(match.group(1)), 4, 1)


def month_start(invoice) -> date:
	return date(int(invoice.billing_year), MONTHS.index(invoice.billing_month) + 1, 1)


# ---------------------------------------------------------------- what was paid


def payee(property) -> frappe._dict:
	settings = frappe.get_cached_doc(SETTINGS)
	building = (
		frappe.db.get_value(
			"Rent Property",
			property,
			["property_name", "address", "city", "pincode", "owner_name", "owner_pan", "owner_address"],
			as_dict=True,
		)
		or frappe._dict()
	)
	own = bool(building.owner_name)
	return frappe._dict(
		name=building.owner_name if own else (settings.landlord_name or building.property_name),
		pan=(building.owner_pan if own else settings.landlord_pan) or None,
		address=(building.owner_address if own else settings.landlord_address) or None,
		property_address=", ".join(
			filter(None, [building.property_name, building.address, building.city, building.pincode])
		),
	)


def rent_months(tenant, fy) -> list[frappe._dict]:
	"""Each month of the financial year the tenant paid rent for."""
	start = fy_start(fy)
	end = date(start.year + 1, 3, 31)
	invoices = frappe.get_all(
		INVOICE,
		filters={"tenant": tenant, "docstatus": 1, "billing_year": ("between", (start.year, end.year))},
		fields=["name", "billing_month", "billing_year", "property", "room", "from_date", "to_date", "pro_rated_rent",
			"discount_amount", "early_discount", "paid_amount", "final_amount"],
	)  # fmt: skip
	months = []
	for inv in invoices:
		if not start <= month_start(inv) <= end:
			continue
		rent = max(flt(inv.pro_rated_rent) - flt(inv.discount_amount) - flt(inv.early_discount), 0)
		paid = min(flt(inv.paid_amount), rent)  # what was paid counts towards the rent first
		if paid <= 0:
			continue
		payments = frappe.get_all(
			"Rent Payment",
			filters={"rent_invoice": inv.name, "docstatus": 1},
			fields=["name", "payment_date", "amount", "mode_of_payment", "reference_no"],
			order_by="payment_date asc",
		)
		months.append(
			frappe._dict(
				invoice=inv.name,
				month=inv.billing_month,
				year=inv.billing_year,
				label=f"{inv.billing_month} {inv.billing_year}",
				from_date=inv.from_date,
				to_date=inv.to_date,
				property=inv.property,
				room=frappe.db.get_value("Tenant Space", inv.room, "room_number") or inv.room,
				rent=flt(rent, 2),
				paid=flt(paid, 2),
				fully_paid=paid >= rent - 0.005,
				payments=payments,
				paid_on=payments[-1].payment_date if payments else None,
				modes=sorted(
					{p.mode_of_payment for p in payments if p.mode_of_payment != "Security Deposit"}
				),
				cash=sum(flt(p.amount) for p in payments if p.mode_of_payment == "Cash"),
			)
		)
	return sorted(months, key=lambda m: (m.year, MONTHS.index(m.month)))


def receipt(tenant, fy, invoice=None) -> frappe._dict:
	"""Everything a receipt shows: one month (invoice) or the whole financial year."""
	start = fy_start(fy)
	months = rent_months(tenant, start)
	if invoice:
		months = [m for m in months if m.invoice == invoice]
	if not months:
		frappe.throw(_("No rent was paid for that period."))
	t = frappe.db.get_value(
		"Tenant", tenant, ["name", "full_name", "mobile_no", "permanent_address"], as_dict=True
	)
	property = months[-1].property
	to = payee(property)
	total = flt(sum(m.paid for m in months), 2)
	yearly = flt(sum(m.paid for m in rent_months(tenant, start)), 2)
	return frappe._dict(
		number=f"RR/{fy_label(start)}/{t.name}"
		+ (f"/{MONTHS.index(months[0].month) + 1:02d}" if invoice else ""),
		date=getdate(nowdate()),
		fy=fy_label(start),
		single=bool(invoice),
		tenant=t,
		payee=to,
		months=months,
		total=total,
		total_words=in_words(total),
		period=months[0].label if invoice else f"{months[0].label} to {months[-1].label}",
		pan_needed=yearly > PAN_LIMIT,
		pan_missing=yearly > PAN_LIMIT and not to.pan,
		stamp=any(m.cash > STAMP_LIMIT for m in months) or (invoice and months[0].cash > STAMP_LIMIT),
		signature=signature_data_url(),
		inr=inr,
	)


def inr(amount) -> str:
	"""₹2,14,265.50: Indian grouping, with paise (pro-rated rent has them)."""
	from rent_management.owner_summary import money

	value = flt(amount, 2)
	rupees, paise = divmod(round(abs(value) * 100), 100)
	whole = money(rupees if value >= 0 else -rupees)
	return whole if not paise else f"{whole}.{paise:02d}"


def in_words(amount) -> str:
	from frappe.utils import money_in_words

	return money_in_words(round(flt(amount)), "INR")


def signature_data_url() -> str | None:
	"""The signature image, inside the receipt (the PDF maker can't open private files)."""
	path = frappe.get_cached_doc(SETTINGS).receipt_signature
	if not path:
		return None
	try:
		file = frappe.get_doc("File", {"file_url": path})
		content = file.get_content(encodings=[])
	except Exception:
		return None
	kind = "png" if path.lower().endswith(".png") else "jpeg"
	return f"data:image/{kind};base64,{base64.b64encode(content).decode()}"


# ---------------------------------------------------------------- the apps


def summary(tenant, fy=None) -> dict:
	"""For the tenant app and the tenant's page: the years and months there are receipts for."""
	start = fy_from_label(fy) if fy else fy_start(nowdate())
	first = frappe.db.get_value(
		INVOICE, {"tenant": tenant, "docstatus": 1}, "posting_date", order_by="posting_date asc"
	)
	years = []
	if first:
		year = fy_start(first)
		while year <= fy_start(nowdate()):
			years.append(fy_label(year))
			year = date(year.year + 1, 4, 1)
	months = rent_months(tenant, start)
	total = flt(sum(m.paid for m in months), 2)
	to = (
		payee(months[-1].property)
		if months
		else payee(frappe.db.get_value(INVOICE, {"tenant": tenant}, "property"))
	)
	return {
		"fy": fy_label(start),
		"years": list(reversed(years)) or [fy_label(start)],
		"months": [
			{k: m[k] for k in ("invoice", "label", "rent", "paid", "fully_paid", "paid_on", "modes")}
			for m in months
		],
		"total": total,
		"payee": {"name": to.name, "pan": to.pan},
		"pan_missing": total > PAN_LIMIT and not to.pan,
	}


def html(tenant, fy, invoice=None) -> str:
	return frappe.render_template(
		"rent_management/templates/rent_receipt.html", {"r": receipt(tenant, fy, invoice)}
	)


def send_pdf(tenant, fy, invoice=None):
	from frappe.utils.pdf import get_pdf

	r = receipt(tenant, fy, invoice)
	page = frappe.render_template("rent_management/templates/rent_receipt.html", {"r": r})
	frappe.local.response.filename = (
		f"Rent-receipt-{r.fy}" + (f"-{r.months[0].month}" if invoice else "") + ".pdf"
	)
	frappe.local.response.filecontent = get_pdf(page, {"page-size": "A4"})
	frappe.local.response.type = "pdf"
