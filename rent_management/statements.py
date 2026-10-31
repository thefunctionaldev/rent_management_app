# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Bank statement matching: upload a bank or UPI statement, confirm the rent in it in one go.

A statement (CSV or Excel, as banks export them) is read into its credits; debits are skipped.
Each credit is matched to rent:

- **Already recorded:** its UTR is on a confirmed payment, or the same line was confirmed from
  an earlier statement (statements can overlap).
- **A payment the tenant reported:** its UTR matches one waiting to be confirmed, or the amount
  and the tenant's name do.
- **A tenant's unpaid bills:** the tenant is found by a UPI ID or name they paid from before
  (learned each time a match is confirmed), their UPI ID for refunds, their mobile number, or
  their name in the narration; then by the amount (one bill, the amount payable now, or all of
  them). An amount only one unpaid bill has is suggested too, with less confidence.

Managers check the suggestions, fix or pick the rest by hand, and confirm: each becomes a Rent
Payment (UPI or bank transfer, with the UTR), over the tenant's bills oldest first if it covers
more than one.
"""

import base64
import csv
import hashlib
import io
import re

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, now_datetime

from rent_management.data_import import normalise, parse_date

STATEMENT = "Bank Statement"
LINE = "Bank Statement Line"
PAYMENT = "Rent Payment"
INVOICE = "Tenant Rent Invoice"
MAX_LINES = 3000

# header words, by what the column holds (the first matching column wins)
COLUMNS = {
	"date": ("txn date", "transaction date", "tran date", "date", "posting date", "value date"),
	"description": ("narration", "description", "particulars", "transaction remarks", "remarks", "details",
		"transaction details"),
	"reference": ("utr", "chq./ref.no.", "chq/ref no", "ref no./cheque no.", "cheque/ref no", "reference",
		"ref no", "ref. no.", "chq no", "cheque no", "transaction id", "upi ref"),
	"credit": ("deposit amt", "deposit", "deposits", "credit amount", "credit", "cr amount", "money in"),
	"debit": ("withdrawal amt", "withdrawal", "withdrawals", "debit amount", "debit", "dr amount", "money out"),
	"amount": ("amount", "transaction amount", "amount (inr)", "txn amount"),
	"type": ("cr/dr", "dr/cr", "dr / cr", "cr / dr", "type", "transaction type", "debit/credit"),
}  # fmt: skip
VPA = re.compile(r"\b[\w.]{2,}@[a-z][a-z0-9]{1,15}\b", re.I)
UTR = re.compile(r"(?<![A-Z0-9])(\d{12}|[A-Z]{4}[A-Z0-9]?\d{10,18}|[A-Z]{4}R\d{12,18})(?![A-Z0-9])")
MOBILE = re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)")
NOISE = {"UPI", "CR", "DR", "IMPS", "NEFT", "RTGS", "INB", "MMT", "TRANSFER", "FROM", "TO", "BY", "PAYMENT",
	"RENT", "P2A", "P2M", "SENT", "USING", "PAYTM", "PHONEPE", "GPAY", "GOOGLE", "PAY", "BANK", "LTD", "NA",
	"THE", "AND", "FOR", "MR", "MRS", "MS", "SHRI", "SMT", "REF", "NO", "IFSC", "AC", "A/C", "OKAXIS", "OKSBI",
	"OKHDFCBANK", "OKICICI", "YBL", "IBL", "AXL", "APL", "UPIIN"}  # fmt: skip
BANK_CODES = {"HDFC", "SBIN", "ICIC", "UTIB", "YESB", "KKBK", "PUNB", "BARB", "CNRB", "UBIN", "IDIB", "IOBA",
	"BKID", "MAHB", "INDB", "IDFB", "FDRL", "KARB", "RATN", "AUBL", "PYTM", "AIRP", "JAKA", "SIBL", "CIUB",
	"KVBL", "TMBL", "DBSS", "SCBL", "CITI", "HSBC", "ESFB", "UCBA", "CBIN", "PSIB", "CSBK", "DLXB", "NSPB"}  # fmt: skip


# ---------------------------------------------------------------- reading a statement


def read_file(filename: str, content: str) -> list[list]:
	data = base64.b64decode(content.split(",", 1)[-1])
	name = filename.lower()
	if name.endswith((".xlsx", ".xlsm")):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		rows = read_xlsx_file_from_attached_file(fcontent=data, read_only=True)
	elif name.endswith(".xls"):
		import xlrd

		try:
			sheet = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
		except xlrd.XLRDError:  # some banks save HTML or text with an .xls name
			rows = html_or_text_rows(data)
		else:
			rows = [
				[
					xlrd.xldate.xldate_as_datetime(cell.value, sheet.book.datemode)
					if cell.ctype == xlrd.XL_CELL_DATE
					else cell.value
					for cell in sheet.row(i)
				]
				for i in range(sheet.nrows)
			]
	elif name.endswith((".csv", ".txt")):
		text = data.decode("utf-8-sig", errors="replace")
		rows = list(csv.reader(io.StringIO(text), dialect=sniff(text)))
	else:
		frappe.throw(
			_(
				"Upload the statement as Excel (.xlsx or .xls) or CSV. Download it from your bank's website or app."
			)
		)
	return [row for row in rows if any(str(cell or "").strip() for cell in row)]  # fmt: skip


def sniff(text):
	try:
		return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
	except csv.Error:
		return csv.excel


def html_or_text_rows(data: bytes) -> list[list]:
	text = data.decode("utf-8", errors="replace")
	if "<table" in text.lower():
		from bs4 import BeautifulSoup

		return [
			[cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
			for tr in BeautifulSoup(text, "html.parser").find_all("tr")
		]
	return list(csv.reader(io.StringIO(text), dialect=sniff(text)))


def find_header(rows) -> tuple[int, dict]:
	"""The row naming the columns (banks put the account details above it) and where each is."""
	for index, row in enumerate(rows[:40]):
		cells = [normalise(cell).rstrip(".:") for cell in row]
		found = {}
		for kind, words in COLUMNS.items():
			for word in (w.rstrip(".:") for w in words):
				col = next((i for i, c in enumerate(cells) if c == word and i not in found.values()), None)
				if col is None:
					col = next(
						(
							i
							for i, c in enumerate(cells)
							if word in c and i not in found.values() and len(c) < 40
						),
						None,
					)
				if col is not None:
					found[kind] = col
					break
		if "date" in found and ("credit" in found or "amount" in found):
			return index, found
	frappe.throw(
		_("Couldn't find the date and credit (deposit) columns. Upload the statement as your bank gives it.")
	)


def to_amount(value) -> float:
	if isinstance(value, int | float):
		return float(value)
	text = str(value or "").upper().replace(",", "").replace("₹", "").replace("INR", "").replace("RS.", "")
	text = text.replace("CR", "").replace("DR", "").strip()
	try:
		return float(text) if text not in ("", "-") else 0.0
	except ValueError:
		return 0.0


def to_date(value):
	if isinstance(value, int | float) and value > 20000:  # an Excel serial date
		from datetime import date, timedelta

		return date(1899, 12, 30) + timedelta(days=int(value))
	try:
		return parse_date(value) if str(value or "").strip() else None
	except Exception:
		return None


def parse(filename: str, content: str) -> tuple[list[dict], int]:
	"""The statement's credits, and how many debits were skipped."""
	rows = read_file(filename, content)
	start, cols = find_header(rows)
	credits, debits = [], 0

	def cell(row, kind):
		col = cols.get(kind)
		return row[col] if col is not None and col < len(row) else None

	for row in rows[start + 1 :]:
		day = to_date(cell(row, "date"))
		if not day:
			continue  # opening balance, totals, the bank's footer
		if "credit" in cols:
			amount, out = to_amount(cell(row, "credit")), to_amount(cell(row, "debit"))
		else:
			value = to_amount(cell(row, "amount"))
			kind = str(cell(row, "type") or cell(row, "amount") or "").upper()
			is_debit = "DR" in kind or "DEBIT" in kind or value < 0
			amount, out = (0, abs(value)) if is_debit else (value, 0)
		if amount <= 0:
			debits += out > 0
			continue
		description = re.sub(r"\s+", " ", str(cell(row, "description") or "")).strip()
		reference = str(cell(row, "reference") or "").strip()
		if isinstance(cell(row, "reference"), float):
			reference = str(int(cell(row, "reference")))
		credits.append(
			{
				"line_date": day,
				"amount": flt(amount, 2),
				"description": description[:1000],
				"reference": utr(reference, description),
				"payer": payer(description),
			}
		)
	if len(credits) > MAX_LINES:
		frappe.throw(_("Upload at most {0} transactions at a time.").format(MAX_LINES))
	return credits, debits


def utr(reference, description) -> str | None:
	ref = re.sub(r"\s", "", reference or "").upper()
	if ref.isdigit():
		ref = ref.lstrip("0")  # banks pad UPI references: 0000412345678901
	if len(ref) >= 6:
		return ref[:140]
	match = UTR.search((description or "").upper())
	return match.group(1) if match else None


def payer(description) -> str | None:
	"""Who paid: their UPI ID, else the name in the narration (UPI/CR/<utr>/RAVI KUMAR/YESB/...)."""
	vpa = VPA.search(description or "")
	if vpa:
		return vpa.group(0).lower()
	words = name_words(description)
	return " ".join(words[:4]).title() or None


def name_words(text) -> list[str]:
	words = re.split(r"[^A-Za-z]+", (text or "").upper())
	return [w for w in words if len(w) >= 3 and w not in NOISE and w not in BANK_CODES]


def line_key(line) -> str:
	"""Same transaction, same key: for statements that overlap."""
	parts = (
		str(getdate(line["line_date"])),
		f"{flt(line['amount']):.2f}",
		line.get("reference") or line["description"],
	)
	return hashlib.sha1("|".join(parts).encode()).hexdigest()[:20]  # fmt: skip


# ---------------------------------------------------------------- matching


def unpaid_bills() -> dict:
	"""Every unpaid bill, by tenant, oldest first."""
	from rent_management import fees

	bills = {}
	for inv in frappe.get_all(
		INVOICE,
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", "tenant", "tenant_name", "billing_month", "billing_year", "outstanding_amount",
			"final_amount", "paid_amount", "late_fee", "early_discount_offer", "early_discount_until",
			"due_date", "next_due_date", "posting_date", "property"],
		order_by="posting_date asc, name asc",
	):  # fmt: skip
		inv.pay_now = fees.payable_now(inv)
		bills.setdefault(str(inv.tenant), []).append(inv)
	return bills


def known_tenants(tenant_names) -> list[frappe._dict]:
	rows = frappe.get_all(
		"Tenant",
		filters={"name": ("in", list(tenant_names) or [""])},
		fields=["name", "full_name", "first_name", "last_name", "mobile_no", "statement_names"],
	)
	refunds = {
		str(r.tenant): r.refund_upi_id
		for r in frappe.get_all(
			"Tenant Space Allotment",
			filters={"tenant": ("in", list(tenant_names) or [""]), "refund_upi_id": ("is", "set")},
			fields=["tenant", "refund_upi_id"],
		)
	}
	for t in rows:
		t.aliases = {a.strip().lower() for a in (t.statement_names or "").splitlines() if a.strip()}
		if refunds.get(str(t.name)):
			t.aliases.add(refunds[str(t.name)].lower())
		t.words = set(name_words(t.full_name))
	return rows


def who_paid(line, tenants) -> tuple[frappe._dict | None, str | None, bool]:
	"""The tenant who sent this credit, why we think so, and whether that's certain."""
	text = line["description"].lower()
	key = (line.get("payer") or "").lower()
	for t in tenants:
		if (key and key in t.aliases) or any(a in text for a in t.aliases if "@" in a):
			return t, _("paid from {0} before").format(key or "this account"), True
	mobiles = set(MOBILE.findall(line["description"]))
	for t in tenants:
		mobile = re.sub(r"\D", "", t.mobile_no or "")[-10:]
		if mobile and mobile in mobiles:
			return t, _("their mobile number is in the narration"), True
	words = set(name_words(line["description"]))
	scored = []
	for t in tenants:
		common = t.words & words
		if not common:
			continue
		full = common == t.words and len(t.words) > 1
		scored.append((2 if full else 1, len(common), t))
	if not scored:
		return None, None, False
	scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
	best = scored[0]
	if len(scored) > 1 and scored[1][:2] == best[:2]:
		return None, None, False  # two tenants with that name: let the manager pick
	return best[2], _("their name is in the narration"), best[0] == 2


def bill_for(amount, bills) -> tuple[frappe._dict | None, str | None]:
	"""The bill this amount pays, and how: "exact" (a bill, what's payable now, or all of them),
	"part" (less than they owe) or "more" (more than they owe)."""
	if not bills:
		return None, None
	for inv in bills:
		if abs(flt(inv.outstanding_amount) - amount) < 0.5 or abs(flt(inv.pay_now) - amount) < 0.5:
			return inv, "exact"
	total = sum(flt(i.outstanding_amount) for i in bills)
	if abs(total - amount) < 0.5:
		return bills[0], "exact"
	return bills[0], "part" if amount < total else "more"


def match(lines) -> None:
	"""Fill in each line's status, tenant, bill and why."""
	bills = unpaid_bills()
	staying = frappe.get_all(
		"Tenant Space Allotment", filters={"docstatus": 1, "status": "Active"}, pluck="tenant"
	)
	tenants = known_tenants({*bills.keys(), *map(str, staying)})
	refs = [line["reference"] for line in lines if line.get("reference")]
	recorded = {
		p.reference_no.upper(): p
		for p in frappe.get_all(
			PAYMENT,
			filters={"reference_no": ("in", refs or [""]), "docstatus": ("<", 2)},
			fields=["name", "reference_no", "docstatus", "tenant", "rent_invoice", "amount", "payment_date"],
		)
	}
	confirmed = set(
		frappe.get_all(
			LINE,
			filters={"line_key": ("in", [line["line_key"] for line in lines] or [""]), "status": "Confirmed"},
			pluck="line_key",
		)
	)
	reported = frappe.get_all(
		PAYMENT,
		filters={"docstatus": 0},
		fields=["name", "reference_no", "tenant", "rent_invoice", "amount", "payment_date"],
	)
	exact_amounts = {}
	for tenant_bills in bills.values():
		for inv in tenant_bills:
			for value in {flt(inv.outstanding_amount, 2), flt(inv.pay_now, 2)}:
				exact_amounts.setdefault(value, set()).add(inv.name)
	invoices = {inv.name: inv for tenant_bills in bills.values() for inv in tenant_bills}
	claimed = set()  # a reported payment or bill suggested once

	for line in lines:
		line.update(status="Unmatched", confidence=None, match_reason=None, tenant=None, rent_invoice=None,
			rent_payment=None)  # fmt: skip
		ref = (line.get("reference") or "").upper()
		done = recorded.get(ref)
		if line["line_key"] in confirmed or (done and done.docstatus == 1):
			line.update(status="Already Recorded", match_reason=_("already recorded"))
			if done:
				line.update(tenant=done.tenant, rent_invoice=done.rent_invoice, rent_payment=done.name)
			continue

		# a payment the tenant reported
		tenant, why, sure = who_paid(line, tenants)
		draft = done if done and done.docstatus == 0 else None
		if not draft:
			draft = next(
				(
					p
					for p in reported
					if p.name not in claimed
					and abs(flt(p.amount) - line["amount"]) < 0.5
					and abs(date_diff(line["line_date"], p.payment_date)) <= 5
					and ((tenant and str(p.tenant) == str(tenant.name)) or (ref and ref == (p.reference_no or "").upper()))
				),
				None,
			)  # fmt: skip
		if draft and draft.name not in claimed:
			claimed.add(draft.name)
			line.update(status="Suggested", confidence="High", tenant=draft.tenant, rent_invoice=draft.rent_invoice,
				rent_payment=draft.name,
				match_reason=_("the tenant reported this payment") + (_(" with this UTR") if ref and ref == (draft.reference_no or "").upper() else ""))  # fmt: skip
			continue

		if tenant:
			inv, fit = bill_for(
				line["amount"], [b for b in bills.get(str(tenant.name), []) if b.name not in claimed]
			)
			if fit == "exact":
				claimed.add(inv.name)
			if fit in ("exact", "part"):
				line.update(status="Suggested", confidence="High" if sure and fit == "exact" else "Medium",
					tenant=tenant.name, rent_invoice=inv.name,
					match_reason=why + ("" if fit == "exact" else _("; less than they owe")))  # fmt: skip
			else:
				line.update(tenant=tenant.name,
					match_reason=why + (_("; more than they owe") if inv else _("; nothing unpaid")))  # fmt: skip

	# then, for the ones nobody is named in: an amount only one unpaid bill still has
	for line in lines:
		if line["status"] != "Unmatched" or line.get("tenant"):
			continue
		candidates = [n for n in exact_amounts.get(flt(line["amount"], 2), ()) if n not in claimed]
		if len(candidates) == 1:
			inv = invoices[candidates[0]]
			claimed.add(inv.name)
			line.update(status="Suggested", confidence="Medium", tenant=inv.tenant, rent_invoice=inv.name,
				match_reason=_("the only unpaid bill of this amount"))  # fmt: skip


# ---------------------------------------------------------------- statements


def upload(filename, content, bank=None) -> str:
	lines, debits = parse(filename, content)
	if not lines:
		frappe.throw(_("No money came in in this statement."))
	for line in lines:
		line["line_key"] = line_key(line)
	match(lines)
	doc = frappe.get_doc(
		{
			"doctype": STATEMENT,
			"bank": (bank or "").strip() or None,
			"file_name": filename[:140],
			"from_date": min(line["line_date"] for line in lines),
			"to_date": max(line["line_date"] for line in lines),
			"credits": len(lines),
			"total_credits": sum(line["amount"] for line in lines),
			"debits": debits,
			"lines": sorted(lines, key=lambda line: line["line_date"]),
		}
	).insert()
	return doc.name


def rematch(name) -> None:
	"""Match the lines not confirmed or ignored again (after recording payments elsewhere)."""
	doc = frappe.get_doc(STATEMENT, name)
	open_lines = [row for row in doc.lines if row.status in ("Unmatched", "Suggested", "Already Recorded")]
	data = [row.as_dict() for row in open_lines]
	match(data)
	for row, new in zip(open_lines, data, strict=True):
		row.update(
			{
				k: new.get(k)
				for k in ("status", "confidence", "match_reason", "tenant", "rent_invoice", "rent_payment")
			}
		)
	doc.save()  # fmt: skip


def get_statements() -> list[dict]:
	rows = frappe.get_all(
		STATEMENT,
		fields=["name", "bank", "file_name", "from_date", "to_date", "credits", "total_credits", "confirmed",
			"creation", "owner"],
		order_by="creation desc",
		limit=50,
	)  # fmt: skip
	counts = {}
	for line in frappe.get_all(
		LINE,
		filters={"parent": ("in", [r.name for r in rows] or [""]), "parenttype": STATEMENT},
		fields=["parent", "status"],
	):
		by_status = counts.setdefault(line.parent, {})
		by_status[line.status] = by_status.get(line.status, 0) + 1
	for r in rows:
		r.counts = counts.get(r.name, {})
	return rows


def get_statement(name) -> dict:
	doc = frappe.get_doc(STATEMENT, name)
	doc.check_permission("read")
	tenants = {str(r.tenant) for r in doc.lines if r.tenant}
	names = {
		str(t.name): t.full_name
		for t in frappe.get_all(
			"Tenant", filters={"name": ("in", list(tenants) or [""])}, fields=["name", "full_name"]
		)
	}
	bills = unpaid_bills()
	invoices = {inv.name: inv for b in bills.values() for inv in b}
	lines = []
	for r in doc.lines:
		inv = invoices.get(r.rent_invoice) if r.rent_invoice else None
		lines.append(
			{
				**{k: r.get(k) for k in ("name", "line_date", "amount", "description", "reference", "payer",
					"status", "confidence", "match_reason", "tenant", "rent_invoice", "rent_payment")},
				"tenant_name": names.get(str(r.tenant)),
				"bill": bill_label(inv) if inv else None,
				"owed": flt(sum(flt(i.outstanding_amount) for i in bills.get(str(r.tenant), []))) if r.tenant else 0,
			}
		)  # fmt: skip
	return {
		"name": doc.name,
		"bank": doc.bank,
		"file_name": doc.file_name,
		"from_date": doc.from_date,
		"to_date": doc.to_date,
		"credits": doc.credits,
		"total_credits": doc.total_credits,
		"debits": doc.debits,
		"lines": lines,
		"tenants": [  # to pick from for the unmatched
			{"tenant": t, "tenant_name": b[0].tenant_name, "owed": flt(sum(flt(i.outstanding_amount) for i in b)),
				"bills": [{"name": i.name, "label": bill_label(i), "outstanding": i.outstanding_amount} for i in b]}
			for t, b in sorted(bills.items(), key=lambda kv: kv[1][0].tenant_name or "")
		],
	}  # fmt: skip


def bill_label(inv) -> str:
	return f"{inv.billing_month} {inv.billing_year} · {frappe.utils.fmt_money(inv.outstanding_amount, currency='INR')} due"


def set_line(name, line, tenant=None, rent_invoice=None, status=None) -> None:
	"""Pick the tenant (and bill) for a line by hand, or ignore it (or bring it back)."""
	doc = frappe.get_doc(STATEMENT, name)
	doc.check_permission("write")
	row = next((r for r in doc.lines if r.name == line), None)
	if not row:
		frappe.throw(_("That transaction isn't in this statement."))
	if row.status == "Confirmed":
		frappe.throw(_("This one is already confirmed."))
	if status == "Ignored":
		row.update({"status": "Ignored", "confidence": None})
	elif status == "Unmatched":
		row.update({"status": "Unmatched", "tenant": None, "rent_invoice": None, "rent_payment": None,
			"confidence": None, "match_reason": None})  # fmt: skip
	elif tenant:
		bills = unpaid_bills().get(str(tenant), [])
		if not bills:
			frappe.throw(
				_("{0} has nothing unpaid.").format(frappe.db.get_value("Tenant", tenant, "full_name"))
			)
		if rent_invoice and rent_invoice not in [b.name for b in bills]:
			frappe.throw(_("Choose one of the tenant's unpaid bills."))
		row.update({"status": "Suggested", "confidence": "High", "tenant": tenant,
			"rent_invoice": rent_invoice or bill_for(row.amount, bills)[0].name, "rent_payment": None,
			"match_reason": _("chosen by {0}").format(frappe.utils.get_fullname())})  # fmt: skip
	doc.save()


def confirm(name, lines) -> dict:
	"""Record the chosen suggestions as payments. Each stands alone: one that fails is reported."""
	doc = frappe.get_doc(STATEMENT, name)
	doc.check_permission("write")
	wanted = set(frappe.parse_json(lines) or [])
	results = {"confirmed": 0, "amount": 0.0, "errors": []}
	for row in doc.lines:
		if row.name not in wanted or row.status != "Suggested":
			continue
		frappe.db.savepoint("statement_line")
		try:
			row.rent_payment = record(doc, row)
			row.status = "Confirmed"
			learn(row)
			results["confirmed"] += 1
			results["amount"] += flt(row.amount)
		except Exception as e:
			frappe.db.rollback(save_point="statement_line")
			frappe.clear_last_message()
			results["errors"].append(
				{"line": row.name, "amount": row.amount, "error": frappe.utils.strip_html(str(e))}
			)
	doc.confirmed = sum(1 for r in doc.lines if r.status == "Confirmed")
	doc.save()
	return results


def record(doc, row) -> str:
	"""The payment(s) for a confirmed line; returns the first."""
	mode = "UPI" if "@" in (row.payer or "") or "UPI" in (row.description or "").upper() else "Bank Transfer"
	remarks = _("From bank statement {0}").format(doc.name)
	if row.rent_payment and frappe.db.get_value(PAYMENT, row.rent_payment, "docstatus") == 0:
		draft = frappe.get_doc(PAYMENT, row.rent_payment)  # the tenant reported it
		if abs(flt(draft.amount) - flt(row.amount)) >= 0.5:
			frappe.throw(_("The tenant reported {0}, the bank shows {1}. Check it on the Payments page.").format(
				frappe.utils.fmt_money(draft.amount, currency="INR"), frappe.utils.fmt_money(row.amount, currency="INR")))  # fmt: skip
		draft.update({"payment_date": row.line_date, "reference_no": draft.reference_no or row.reference,
			"mode_of_payment": draft.mode_of_payment if draft.mode_of_payment in ("UPI", "Bank Transfer") else mode})  # fmt: skip
		draft.submit()
		return draft.name

	bills = unpaid_bills().get(str(row.tenant), [])
	if not bills:
		frappe.throw(_("{0} has nothing unpaid any more.").format(frappe.db.get_value("Tenant", row.tenant, "full_name")))  # fmt: skip
	order = sorted(bills, key=lambda b: b.name != row.rent_invoice)  # the chosen bill first, then the oldest
	left = flt(row.amount, 2)
	if left - sum(flt(b.outstanding_amount) for b in bills) >= 0.5:
		frappe.throw(_("{0} is more than {1} owes ({2}). Record it on the Payments page.").format(
			frappe.utils.fmt_money(row.amount, currency="INR"), bills[0].tenant_name,
			frappe.utils.fmt_money(sum(flt(b.outstanding_amount) for b in bills), currency="INR")))  # fmt: skip
	first = None
	for bill in order:
		if left < 0.005:
			break
		amount = min(left, flt(bill.outstanding_amount))
		payment = frappe.get_doc(
			{
				"doctype": PAYMENT,
				"tenant": row.tenant,
				"rent_invoice": bill.name,
				"amount": amount,
				"mode_of_payment": mode,
				"payment_date": row.line_date,
				"reference_no": row.reference,
				"remarks": remarks,
			}
		).insert()
		payment.submit()
		first = first or payment.name
		left = flt(left - amount, 2)
	return first


def learn(row) -> None:
	"""Remember who this tenant pays from, so next month's statement matches by itself."""
	key = (row.payer or "").strip()
	if not key or not row.tenant:
		return
	names = frappe.db.get_value("Tenant", row.tenant, "statement_names") or ""
	known = [n.strip() for n in names.splitlines() if n.strip()]
	if key.lower() not in {n.lower() for n in known}:
		frappe.db.set_value("Tenant", row.tenant, "statement_names", "\n".join([*known, key][-10:]), update_modified=False)  # fmt: skip


def delete(name) -> None:
	"""Remove an upload. Payments already confirmed from it stay."""
	frappe.delete_doc(STATEMENT, name)
