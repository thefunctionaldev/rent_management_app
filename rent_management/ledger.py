# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""A tenant's statement (every bill and payment, with the running balance, and their deposit) and
a no-dues certificate.

The statement lists bills on their posting date (the amount billed: rent, charges, late fees,
less discounts) and payments on the day they were made, so the balance at the end is what they
owe. The deposit is shown on its own: collected, what was taken from it and what was refunded.
Both apps show it and download it as a PDF, for any period.

A no-dues certificate says the tenant owes nothing: nothing unpaid, no bill being prepared, no
payment waiting to be confirmed and, once they've moved out, their deposit settled with nothing
left for them to pay. Tenants often need one for their next landlord, a company or a college.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

INVOICE = "Tenant Rent Invoice"
PAYMENT = "Rent Payment"
ALLOTMENT = "Tenant Space Allotment"


def bill_detail(inv, charges) -> str:
	parts = [_("Rent {0}").format(money(inv.pro_rated_rent))]
	parts += [f"{c.description or _(c.charge_type)} {money(c.amount)}" for c in charges]
	if flt(inv.discount_amount):
		parts.append(_("discount -{0}").format(money(inv.discount_amount)))
	if flt(inv.late_fee):
		parts.append(_("late fee {0}").format(money(inv.late_fee)))
	if flt(inv.early_discount):
		parts.append(_("paid early -{0}").format(money(inv.early_discount)))
	return " · ".join(parts)


def money(amount) -> str:
	from rent_management.receipts import inr

	return inr(amount)


def statement(tenant, from_date=None, to_date=None) -> dict:
	"""Bills and payments in date order with the running balance, and the deposit."""
	from_date = getdate(from_date) if from_date else None
	to_date = getdate(to_date or nowdate())
	invoices = frappe.get_all(
		INVOICE,
		filters={"tenant": tenant, "docstatus": 1, "posting_date": ("<=", to_date)},
		fields=["name", "billing_month", "billing_year", "posting_date", "pro_rated_rent", "discount_amount",
			"late_fee", "early_discount", "final_amount", "room", "property"],
		order_by="posting_date asc, name asc",
	)  # fmt: skip
	charges = {}
	for c in frappe.get_all(
		"Tenant Rent Invoice Charge",
		filters={"parent": ("in", [i.name for i in invoices] or [""]), "parenttype": INVOICE},
		fields=["parent", "charge_type", "description", "amount"],
		order_by="idx asc",
	):
		charges.setdefault(c.parent, []).append(c)
	payments = frappe.get_all(
		PAYMENT,
		filters={"tenant": tenant, "docstatus": 1, "payment_date": ("<=", to_date)},
		fields=["name", "payment_date", "amount", "mode_of_payment", "reference_no", "rent_invoice"],
		order_by="payment_date asc, creation asc",
	)
	rows = [
		{"date": i.posting_date, "kind": "bill", "ref": i.name, "label": _("{0} {1} bill").format(_(i.billing_month), i.billing_year),
			"detail": bill_detail(i, charges.get(i.name, [])), "debit": flt(i.final_amount), "credit": 0}
		for i in invoices
	] + [
		{"date": p.payment_date, "kind": "payment", "ref": p.name,
			"label": _("Paid from deposit") if p.mode_of_payment == "Security Deposit" else _("Paid by {0}").format(_(p.mode_of_payment)),
			"detail": " · ".join(filter(None, [p.reference_no and _("Ref. {0}").format(p.reference_no), p.rent_invoice])),
			"debit": 0, "credit": flt(p.amount)}
		for p in payments
	]  # fmt: skip
	rows.sort(key=lambda r: (getdate(r["date"]), r["kind"] != "bill"))
	opening, balance, shown = 0.0, 0.0, []
	for row in rows:
		balance = flt(balance + row["debit"] - row["credit"], 2)
		if from_date and getdate(row["date"]) < from_date:
			opening = balance
			continue
		shown.append({**row, "balance": balance})
	t = frappe.db.get_value("Tenant", tenant, ["name", "full_name", "mobile_no", "email_id"], as_dict=True)
	return {
		"tenant": t,
		"from_date": from_date or (getdate(rows[0]["date"]) if rows else to_date),
		"to_date": to_date,
		"opening": opening,
		"rows": shown,
		"billed": flt(sum(r["debit"] for r in shown), 2),
		"paid": flt(sum(r["credit"] for r in shown), 2),
		"balance": balance,
		"deposits": deposits(tenant),
		"stay": stay_summary(tenant),
	}


def deposits(tenant) -> list[dict]:
	out = []
	for s in frappe.get_all(
		ALLOTMENT,
		filters={"tenant": tenant, "docstatus": 1, "security_deposit": (">", 0)},
		fields=["name", "room", "allotment_date", "vacate_date", "security_deposit", "deposit_collected",
			"deposit_collected_on", "deposit_settlement"],
		order_by="allotment_date asc",
	):  # fmt: skip
		row = {
			"stay": s.name,
			"room": frappe.db.get_value("Tenant Space", s.room, "room_number") or s.room,
			"amount": flt(s.security_deposit),
			"collected": bool(s.deposit_collected),
			"collected_on": s.deposit_collected_on,
		}
		if s.deposit_settlement:
			d = frappe.get_doc("Security Deposit Settlement", s.deposit_settlement)
			row["settlement"] = {
				"date": d.settlement_date,
				"deductions": [{"reason": x.reason, "description": x.description, "amount": flt(x.amount)} for x in d.deductions],
				"rent_adjusted": flt(d.rent_adjusted),
				"refund": flt(d.refund_amount),
				"owes": flt(d.balance_payable_by_tenant),
				"mode": d.mode_of_refund,
				"reference": d.reference_no,
			}  # fmt: skip
		out.append(row)
	return out


def stay_summary(tenant) -> dict | None:
	"""Their latest stay: where and when."""
	s = frappe.get_all(
		ALLOTMENT,
		filters={"tenant": tenant, "docstatus": 1},
		fields=[
			"name",
			"room",
			"property",
			"allotment_date",
			"vacate_date",
			"status",
			"expected_vacate_date",
		],
		order_by="allotment_date desc",
		limit=1,
	)
	if not s:
		return None
	s = s[0]
	first = frappe.db.get_value(ALLOTMENT, {"tenant": tenant, "docstatus": 1}, "allotment_date", order_by="allotment_date asc")  # fmt: skip
	return {
		"stay": s.name,
		"property": s.property,
		"room": frappe.db.get_value("Tenant Space", s.room, "room_number") or s.room,
		"since": first,
		"until": s.vacate_date,
		"active": s.status == "Active",
	}


# ---------------------------------------------------------------- no dues


def no_dues(tenant) -> dict:
	"""Whether a no-dues certificate can be given, and if not, why."""
	reasons = []
	unpaid = flt(
		sum(frappe.get_all(INVOICE, filters={"tenant": tenant, "docstatus": 1}, pluck="outstanding_amount")),
		2,
	)
	if unpaid > 0.005:
		reasons.append(_("{0} is unpaid").format(money(unpaid)))
	if frappe.db.exists(INVOICE, {"tenant": tenant, "docstatus": 0}):
		reasons.append(_("a bill is being prepared"))
	if frappe.db.exists(PAYMENT, {"tenant": tenant, "docstatus": 0}):
		reasons.append(_("a payment is waiting to be confirmed"))
	stay = stay_summary(tenant)
	if not stay:
		reasons.append(_("there is no stay on record"))
	for d in deposits(tenant):
		s = d.get("settlement")
		if s and s["owes"] > 0.005:
			reasons.append(_("{0} is still owed after the deposit was settled").format(money(s["owes"])))
		elif not s and d["collected"] and stay and not stay["active"]:
			reasons.append(_("the deposit isn't settled yet"))
	return {"eligible": not reasons, "reasons": reasons, "stay": stay}


def certificate(tenant) -> frappe._dict:
	from rent_management import receipts

	status = no_dues(tenant)
	if not status["eligible"]:
		frappe.throw(
			_("A no-dues certificate can't be given yet: {0}.").format(", ".join(status["reasons"])),
			title=_("Dues pending"),
		)
	stay = status["stay"]
	t = frappe.db.get_value("Tenant", tenant, ["name", "full_name", "mobile_no"], as_dict=True)
	paid = flt(sum(frappe.get_all(PAYMENT, filters={"tenant": tenant, "docstatus": 1}, pluck="amount")), 2)
	refunded = [d["settlement"] for d in deposits(tenant) if d.get("settlement")]
	today = getdate(nowdate())
	return frappe._dict(
		number=f"ND/{receipts.fy_label(receipts.fy_start(today))}/{t.name}",
		date=today,
		tenant=t,
		stay=stay,
		payee=receipts.payee(stay["property"]),
		paid=paid,
		deposit=refunded[-1] if refunded else None,
		signature=receipts.signature_data_url(),
		inr=receipts.inr,
	)


# ---------------------------------------------------------------- PDFs


def statement_pdf(tenant, from_date=None, to_date=None):
	from rent_management import pdf, receipts

	data = statement(tenant, from_date, to_date)
	data["payee"] = receipts.payee(data["stay"]["property"]) if data["stay"] else None
	page = frappe.render_template(
		"rent_management/templates/tenant_statement.html", {"s": frappe._dict(data), "inr": receipts.inr}
	)
	send(
		f"Statement-{(data['tenant'].full_name or tenant).replace(' ', '-')}",
		pdf.of_html(page, {"page-size": "A4"}),
	)


def certificate_pdf(tenant):
	from rent_management import pdf

	c = certificate(tenant)
	page = frappe.render_template("rent_management/templates/no_dues.html", {"c": c})
	send(
		f"No-dues-{(c.tenant.full_name or tenant).replace(' ', '-')}", pdf.of_html(page, {"page-size": "A4"})
	)


def send(filename, content):
	frappe.local.response.filename = f"{filename}.pdf"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"
