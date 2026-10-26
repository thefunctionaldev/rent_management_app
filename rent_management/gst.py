# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""GST helpers for the tax invoices of subscription payments."""

import re

import frappe
from frappe import _
from frappe.utils import flt

STATE_CODES = {
	"01": "Jammu and Kashmir",
	"02": "Himachal Pradesh",
	"03": "Punjab",
	"04": "Chandigarh",
	"05": "Uttarakhand",
	"06": "Haryana",
	"07": "Delhi",
	"08": "Rajasthan",
	"09": "Uttar Pradesh",
	"10": "Bihar",
	"11": "Sikkim",
	"12": "Arunachal Pradesh",
	"13": "Nagaland",
	"14": "Manipur",
	"15": "Mizoram",
	"16": "Tripura",
	"17": "Meghalaya",
	"18": "Assam",
	"19": "West Bengal",
	"20": "Jharkhand",
	"21": "Odisha",
	"22": "Chhattisgarh",
	"23": "Madhya Pradesh",
	"24": "Gujarat",
	"26": "Dadra and Nagar Haveli and Daman and Diu",
	"27": "Maharashtra",
	"29": "Karnataka",
	"30": "Goa",
	"31": "Lakshadweep",
	"32": "Kerala",
	"33": "Tamil Nadu",
	"34": "Puducherry",
	"35": "Andaman and Nicobar Islands",
	"36": "Telangana",
	"37": "Andhra Pradesh",
	"38": "Ladakh",
	"97": "Other Territory",
}

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_digit(first_14: str) -> str:
	total = 0
	for i, char in enumerate(first_14):
		product = GSTIN_CHARS.index(char) * (2 if i % 2 else 1)
		total += product // 36 + product % 36
	return GSTIN_CHARS[(36 - total % 36) % 36]


def validate_gstin(gstin: str) -> str:
	"""Normalise and validate a GSTIN, returning it in upper case."""
	gstin = (gstin or "").strip().upper()
	if not gstin:
		return ""
	if not GSTIN_PATTERN.match(gstin) or gstin[:2] not in STATE_CODES:
		frappe.throw(_("{0} is not a valid GSTIN.").format(gstin))
	if gstin_check_digit(gstin[:14]) != gstin[14]:
		frappe.throw(_("GSTIN {0} has a wrong check digit. Please check for typos.").format(gstin))
	return gstin


def state_from_gstin(gstin: str) -> str | None:
	return STATE_CODES.get((gstin or "")[:2])


def same_state(a: str | None, b: str | None) -> bool:
	return bool(a and b) and a.strip().lower() == b.strip().lower()


def get_vendor() -> frappe._dict:
	"""Your business details, from `rent_vendor` in common_site_config.json."""
	vendor = frappe._dict(frappe.conf.get("rent_vendor") or {})
	vendor.name = vendor.name or frappe.conf.get("rent_subscription_brand") or "Rent Management"
	vendor.gstin = (vendor.gstin or "").upper()
	vendor.state = vendor.state or state_from_gstin(vendor.gstin)
	return vendor


def get_rent_vendor() -> frappe._dict:
	"""For print formats (registered as a Jinja method in hooks.py)."""
	return get_vendor()


def gst_rate() -> float:
	return flt(frappe.conf.get("rent_gst_rate", 18))


def prices_include_gst() -> bool:
	return bool(frappe.conf.get("rent_prices_include_gst", 1))


def payable_amount(price: float) -> float:
	"""What the customer pays for a plan price: GST is added on top only when prices
	are configured as exclusive of GST and you are GST registered."""
	if get_vendor().gstin and not prices_include_gst():
		return flt(price * (1 + gst_rate() / 100), 2)
	return flt(price, 2)


def get_breakup(total: float, customer_state: str | None) -> dict:
	"""Split an amount paid into taxable value and CGST + SGST (same state) or IGST."""
	vendor = get_vendor()
	total = flt(total, 2)
	if not vendor.gstin:
		# not GST registered: a plain invoice without tax
		return {
			"gst_rate": 0,
			"taxable_value": total,
			"cgst_amount": 0,
			"sgst_amount": 0,
			"igst_amount": 0,
			"tax_amount": 0,
		}

	rate = gst_rate()
	taxable = flt(total / (1 + rate / 100), 2)
	tax = flt(total - taxable, 2)
	place_of_supply = customer_state or vendor.state
	if same_state(place_of_supply, vendor.state):
		cgst = flt(tax / 2, 2)
		split = {"cgst_amount": cgst, "sgst_amount": flt(tax - cgst, 2), "igst_amount": 0}
	else:
		split = {"cgst_amount": 0, "sgst_amount": 0, "igst_amount": tax}
	return {"gst_rate": rate, "taxable_value": taxable, "tax_amount": tax, **split}
