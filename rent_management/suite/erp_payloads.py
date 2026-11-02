"""Pure ERPNext draft payloads. No outbound requests or auto-submission here."""


def journal(settings, key, posting_date, debit, credit, amount, remark, party=None, reference=None):
	rows = [
		{"account": debit, "debit_in_account_currency": amount, "credit_in_account_currency": 0},
		{"account": credit, "debit_in_account_currency": 0, "credit_in_account_currency": amount},
	]
	for row in rows:
		row["cost_center"] = settings.get("cost_center")
		if row["account"] == settings.get("receivable_account") and party:
			row.update(party_type="Customer", party=party)
			if reference:
				row.update(reference_type="Sales Invoice", reference_name=reference)
	return {
		"doctype": "Journal Entry",
		"voucher_type": "Journal Entry",
		"company": settings["company"],
		"posting_date": posting_date,
		"user_remark": remark,
		"custom_rent_sync_key": key,
		"accounts": rows,
	}


def invoice(settings, key, source, customer):
	return {
		"doctype": "Sales Invoice",
		"company": settings["company"],
		"customer": customer,
		"posting_date": str(source["posting_date"]),
		"due_date": str(source.get("due_date") or source["posting_date"]),
		"currency": settings["currency"],
		"debit_to": settings["receivable_account"],
		"custom_rent_sync_key": key,
		"remarks": f"Rent invoice {source['name']}",
		"taxes": [],
		"items": [
			{
				"item_code": settings["rent_item"],
				"qty": 1,
				"rate": source["final_amount"],
				"income_account": settings["income_account"],
				"cost_center": settings.get("cost_center"),
			}
		],
		"disable_rounded_total": 1,
	}


def receipt(settings, key, source, customer, remote_invoice):
	amount = source["amount"]
	if source["mode_of_payment"] == "Security Deposit":
		return journal(
			settings,
			key,
			str(source["payment_date"]),
			settings["deposit_account"],
			settings["receivable_account"],
			amount,
			f"Deposit applied: {source['name']}",
			customer,
			remote_invoice,
		)
	return {
		"doctype": "Payment Entry",
		"company": settings["company"],
		"payment_type": "Receive",
		"party_type": "Customer",
		"party": customer,
		"posting_date": str(source["payment_date"]),
		"paid_from": settings["receivable_account"],
		"paid_to": settings["cash_account"]
		if source["mode_of_payment"] == "Cash"
		else settings["bank_account"],
		"paid_amount": amount,
		"received_amount": amount,
		"source_exchange_rate": 1,
		"target_exchange_rate": 1,
		"reference_no": source.get("reference_no") or source["name"],
		"reference_date": str(source["payment_date"]),
		"custom_rent_sync_key": key,
		"references": [
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": remote_invoice,
				"allocated_amount": amount,
			}
		],
	}
