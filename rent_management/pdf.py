# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""PDFs (agreements, invoices, rent receipts, the verification form), made with Chrome.

Chrome runs everywhere, Apple-chip Macs included, where the Intel-only wkhtmltopdf won't
without Rosetta. Frappe downloads it into the bench on first use (`bench setup-chrome` does
it ahead of time), or uses `chromium_path` from common_site_config.json. If Chrome can't
start, wkhtmltopdf is tried instead.
"""

import frappe
from frappe import _

CHROME = "chrome"


def of_print(doctype, name, print_format) -> bytes:
	"""A document's print format as a PDF."""
	return _make(
		lambda: frappe.get_print(doctype, name, print_format=print_format, as_pdf=True, pdf_generator=CHROME),
		lambda: frappe.get_print(
			doctype, name, print_format=print_format, as_pdf=True, pdf_generator="wkhtmltopdf"
		),
	)


def of_html(html, options=None) -> bytes:
	"""A whole HTML page as a PDF."""
	from frappe.utils.pdf import get_chrome_pdf, get_pdf

	return _make(
		lambda: get_chrome_pdf(None, html, dict(options or {}), None, CHROME),
		lambda: get_pdf(html, dict(options or {})),
	)


def _make(chrome, wkhtmltopdf) -> bytes:
	try:
		pdf = chrome()
		if pdf:
			return pdf
	except frappe.PermissionError:
		raise
	except Exception:
		frappe.clear_last_message()
		frappe.log_error(title=_("Could not make a PDF with Chrome"))
	try:
		return wkhtmltopdf()
	except OSError:
		frappe.log_error(title=_("Could not make a PDF with wkhtmltopdf"))
		frappe.throw(
			_("Couldn't make the PDF. Run 'bench setup-chrome' on the server, then try again."),
			title=_("PDF maker missing"),
		)
