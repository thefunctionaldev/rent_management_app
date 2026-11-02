import hashlib
import ipaddress
import json
import socket
from urllib.parse import quote, urlsplit

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, now_datetime

from rent_management import access
from rent_management.suite import erp_payloads
from rent_management.suite.common import admin, locked, manager, note_failure, own_fields, positive, save

SETTINGS = "Rent Integration Settings"
DT = "Rent ERP Sync"
SOURCES = {"Tenant Rent Invoice", "Rent Payment", "Property Expense", "Tenant Space Allotment"}
PUBLIC_FIELDS = (
	"enabled",
	"base_url",
	"company",
	"currency",
	"rent_item",
	"income_account",
	"expense_account",
	"deposit_account",
	"receivable_account",
	"bank_account",
	"cash_account",
	"cost_center",
	"customer_group",
	"territory",
)


def validate_url(url, resolve=True):
	parts = urlsplit(url or "")
	if (
		parts.scheme != "https"
		or not parts.hostname
		or parts.username
		or parts.password
		or parts.path not in ("", "/")
		or parts.query
		or parts.fragment
		or parts.port not in (None, 443)
	):
		raise ValueError("Use an HTTPS ERPNext hostname without credentials, ports or a path.")
	if resolve:
		addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
		if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
			raise ValueError("ERPNext must resolve to public network addresses.")
	return url.rstrip("/")


def remote(settings, method, path, **kwargs):
	base = validate_url(settings.base_url)
	key = settings.get_password("api_key", raise_exception=False)
	secret = settings.get_password("api_secret", raise_exception=False)
	if not key or not secret:
		raise ValueError("ERPNext API credentials are missing.")
	response = requests.request(
		method,
		base + path,
		headers={"Authorization": f"token {key}:{secret}"},
		timeout=(10, 30),
		allow_redirects=False,
		**kwargs,
	)
	if not 200 <= response.status_code < 300:
		raise ValueError(
			f"ERPNext returned HTTP {response.status_code}; check permissions, mappings and remote logs."
		)
	return response.json().get("data")


def find_remote(settings, doctype, key):
	rows = remote(
		settings,
		"GET",
		f"/api/resource/{quote(doctype)}",
		params={
			"filters": json.dumps([["custom_rent_sync_key", "=", key]]),
			"fields": json.dumps(["name", "docstatus"]),
			"limit_page_length": 2,
		},
	)
	if len(rows) > 1:
		raise ValueError("Duplicate sync keys exist in ERPNext. Resolve them before retrying.")
	return rows[0] if rows else None


def customer(settings, tenant):
	key = sync_key("Tenant", str(tenant))
	existing = find_remote(settings, "Customer", key)
	if existing:
		return existing["name"]
	name = frappe.db.get_value("Tenant", tenant, "full_name")
	return remote(
		settings,
		"POST",
		"/api/resource/Customer",
		json={
			"customer_name": name,
			"customer_type": "Individual",
			"customer_group": settings.customer_group,
			"territory": settings.territory,
			"custom_rent_sync_key": key,
		},
	)["name"]


def sync_key(doctype, name):
	return hashlib.sha256(f"{frappe.local.site}:{doctype}:{name}".encode()).hexdigest()


def source_doc(doctype, name):
	if doctype not in SOURCES:
		frappe.throw(_("This source type is not supported."))
	doc = frappe.get_doc(doctype, name)
	if doctype != "Property Expense" and doc.docstatus != 1:
		frappe.throw(_("Only submitted sources can be synced."))
	if doctype == "Tenant Space Allotment":
		if not doc.deposit_collected:
			frappe.throw(_("Record the deposit collection first."))
		if doc.get("transferred_from"):
			frappe.throw(
				_(
					"Transferred deposits must be reconciled manually in ERPNext to avoid recording them twice."
				)
			)
	return doc


@frappe.whitelist()
def overview():
	manager()
	settings = frappe.get_single(SETTINGS)
	values = (
		{f: settings.get(f) for f in PUBLIC_FIELDS}
		if "System Manager" in frappe.get_roles()
		else {"enabled": settings.enabled}
	)
	values.update(
		api_key_set=bool(settings.get_password("api_key", raise_exception=False)),
		api_secret_set=bool(settings.get_password("api_secret", raise_exception=False)),
	)
	rows = frappe.get_all(
		DT,
		fields=[
			"name",
			"source_doctype",
			"source_name",
			"source_modified",
			"status",
			"remote_doctype",
			"remote_name",
			"attempts",
			"last_attempt",
			"error",
		],
		order_by="creation desc",
		limit_page_length=200,
	)
	for row in rows:
		row.source_changed = str(frappe.db.get_value(row.source_doctype, row.source_name, "modified")) != str(
			row.source_modified
		)
	return {
		"settings": values,
		"rows": rows,
		"source_types": sorted(SOURCES),
		"can_configure": "System Manager" in frappe.get_roles(),
	}


def verify_settings(settings):
	for field in (
		"company",
		"currency",
		"rent_item",
		"income_account",
		"expense_account",
		"deposit_account",
		"receivable_account",
		"bank_account",
		"cash_account",
		"customer_group",
		"territory",
	):
		if not settings.get(field):
			raise ValueError(f"Configure {field.replace('_', ' ')} first.")
	# Unique remote keys are required: retries can reconcile a successful POST whose response was lost.
	for dt in ("Customer", "Sales Invoice", "Payment Entry", "Journal Entry"):
		fields = remote(
			settings,
			"GET",
			"/api/resource/Custom%20Field",
			params={
				"filters": json.dumps({"dt": dt, "fieldname": "custom_rent_sync_key"}),
				"fields": json.dumps(["fieldtype", "unique"]),
				"limit_page_length": 1,
			},
		)
		if not fields or fields[0]["fieldtype"] != "Data" or not fields[0]["unique"]:
			raise ValueError(f"Add a unique Data custom_rent_sync_key field to ERPNext {dt} first.")
	company = remote(settings, "GET", f"/api/resource/Company/{quote(settings.company, safe='')}")
	if company["default_currency"] != settings.currency:
		raise ValueError("ERPNext company currency must match the configured currency.")
	for field in (
		"income_account",
		"expense_account",
		"deposit_account",
		"receivable_account",
		"bank_account",
		"cash_account",
	):
		account = remote(settings, "GET", f"/api/resource/Account/{quote(settings.get(field), safe='')}")
		if (
			account.get("is_group")
			or account.get("company") != settings.company
			or account.get("account_currency") != settings.currency
		):
			raise ValueError(f"Invalid company or currency on {field}.")

		expected_root = {
			"income_account": "Income",
			"expense_account": "Expense",
			"deposit_account": "Liability",
			"receivable_account": "Asset",
			"bank_account": "Asset",
			"cash_account": "Asset",
		}[field]
		if account.get("root_type") != expected_root:
			raise ValueError(f"Invalid account classification on {field}.")
		account_type = {
			"receivable_account": "Receivable",
			"bank_account": "Bank",
			"cash_account": "Cash",
		}.get(field)
		if account_type and account.get("account_type") != account_type:
			raise ValueError(f"Expected a {account_type} account for {field}.")
	item = remote(settings, "GET", f"/api/resource/Item/{quote(settings.rent_item, safe='')}")
	if item.get("disabled") or item.get("is_stock_item") or not item.get("is_sales_item"):
		raise ValueError("Choose an enabled non-stock sales item for rent.")
	for doctype, name in (("Customer Group", settings.customer_group), ("Territory", settings.territory)):
		remote(settings, "GET", f"/api/resource/{quote(doctype)}/{quote(name, safe='')}")
	if settings.cost_center:
		center = remote(
			settings, "GET", f"/api/resource/Cost%20Center/{quote(settings.cost_center, safe='')}"
		)
		if center.get("company") != settings.company or center.get("is_group"):
			raise ValueError("Choose a non-group cost center in the configured company.")


@frappe.whitelist(methods=["POST"])
def configure(data):
	admin()
	data = frappe.parse_json(data)
	settings = frappe.get_single(SETTINGS)
	old_url, old_company = settings.base_url, settings.company
	settings.update(own_fields(data, PUBLIC_FIELDS))
	if frappe.db.exists(DT) and (settings.base_url != old_url or settings.company != old_company):
		frappe.throw(
			_("A site with sync history cannot change its destination. Use a separate integration site.")
		)
	if settings.base_url:
		validate_url(settings.base_url, resolve=False)
	for field in ("api_key", "api_secret"):
		if data.get(field):
			settings.set(field, data[field])
	if settings.enabled:
		# Validate saved encrypted credentials via the stored document after save. Any error rolls back.
		save(settings)
		verify_settings(frappe.get_single(SETTINGS))
	else:
		save(settings)
	return {"saved": True}


@frappe.whitelist(methods=["POST"])
def queue(source_doctype, source_name):
	manager()
	settings = frappe.get_single(SETTINGS)
	if not settings.enabled:
		frappe.throw(_("Configure and enable the ERPNext connection first."))
	doc = source_doc(source_doctype, source_name)
	doc.check_permission("read")
	currency = frappe.db.get_default("currency") or "INR"
	if currency != settings.currency:
		frappe.throw(_("Source and ERPNext currencies must match."))
	key = sync_key(source_doctype, source_name)
	existing = frappe.db.get_value(DT, {"sync_key": key}, "name")
	if existing:
		return existing
	return save(
		frappe.get_doc(
			{
				"doctype": DT,
				"source_doctype": source_doctype,
				"source_name": source_name,
				"source_modified": doc.modified,
				"sync_key": key,
				"status": "Queued",
				"requested_by": frappe.session.user,
			}
		)
	).name


def payload(settings, row, doc):
	s = {k: settings.get(k) for k in PUBLIC_FIELDS}
	if doc.doctype == "Tenant Rent Invoice":
		return erp_payloads.invoice(s, row.sync_key, doc.as_dict(), customer(settings, doc.tenant))
	if doc.doctype == "Rent Payment":
		invoice = find_remote(settings, "Sales Invoice", sync_key("Tenant Rent Invoice", doc.rent_invoice))
		if not invoice or invoice.get("docstatus") != 1:
			raise ValueError(
				"Sync and submit the corresponding ERPNext Sales Invoice before syncing its payment."
			)
		return erp_payloads.receipt(
			s, row.sync_key, doc.as_dict(), customer(settings, doc.tenant), invoice["name"]
		)
	if doc.doctype == "Property Expense":
		bank = settings.cash_account if doc.mode_of_payment == "Cash" else settings.bank_account
		return erp_payloads.journal(
			s,
			row.sync_key,
			str(doc.expense_date),
			settings.expense_account,
			bank,
			positive(doc.amount),
			f"Property expense {doc.name}: {doc.description or doc.category}",
		)
	return erp_payloads.journal(
		s,
		row.sync_key,
		str(doc.deposit_collected_on),
		settings.bank_account,
		settings.deposit_account,
		positive(doc.security_deposit),
		f"Security deposit collected: {doc.name}. Verify collection account before submission.",
	)


def process(name):
	settings = frappe.get_single(SETTINGS)
	if not settings.enabled:
		return
	row = locked(DT, name)
	if row.status == "Synced":
		return
	row.attempts, row.last_attempt = cint(row.attempts) + 1, now_datetime()
	try:
		if not access.is_manager(row.requested_by) or not frappe.db.get_value(
			"User", row.requested_by, "enabled"
		):
			raise ValueError("Requester no longer has manager access.")
		doc = source_doc(row.source_doctype, row.source_name)
		if str(doc.modified) != str(row.source_modified):
			raise ValueError(
				"Source changed since it was queued. Reconcile manually; this snapshot will not be overwritten."
			)
		remote_type = {
			"Tenant Rent Invoice": "Sales Invoice",
			"Rent Payment": "Journal Entry"
			if doc.get("mode_of_payment") == "Security Deposit"
			else "Payment Entry",
		}.get(doc.doctype, "Journal Entry")
		existing = find_remote(settings, remote_type, row.sync_key)
		if existing and existing.get("docstatus") == 2:
			raise ValueError(
				"The ERPNext document was cancelled. Reconcile manually; it will not be recreated."
			)
		if not existing:
			body = payload(settings, row, doc)
			row.payload = frappe.as_json(body)
			existing = remote(settings, "POST", f"/api/resource/{quote(remote_type)}", json=body)
		row.status, row.remote_doctype, row.remote_name, row.error = (
			"Synced",
			remote_type,
			existing["name"],
			None,
		)
	except (requests.RequestException, ValueError, frappe.ValidationError):
		# Never persist auth headers, secrets, or arbitrary remote error bodies.
		row.status = "Failed"
		note_failure()
		row.error = "Sync failed. Check mappings, source version, submitted invoice dependencies and ERPNext permissions. Retry reconciles any document already created."
	save(row)


def process_queue():
	if not frappe.db.get_single_value(SETTINGS, "enabled"):
		return
	for name in frappe.get_all(
		DT, filters={"status": "Queued"}, pluck="name", order_by="creation", limit_page_length=50
	):
		process(name)


@frappe.whitelist(methods=["POST"])
def retry(name):
	manager()
	row = locked(DT, name)
	if row.status == "Synced":
		frappe.throw(_("This record is already synced. Review changes in ERPNext manually."))
	row.status = "Queued"
	save(row)
	return row.name
