import frappe

# new Rent Management Settings fields; Frappe doesn't apply defaults to an existing Single
DEFAULTS = {
	"send_reminders": 1,
	"remind_days_before": 3,
	"remind_on_due_date": 1,
	"overdue_reminder_interval": 3,
	"overdue_reminder_limit": 3,
	"send_receipts": 1,
	"notify_by_whatsapp": 1,
	"notify_by_email": 1,
}


def execute():
	saved = set(
		frappe.db.sql_list("select field from `tabSingles` where doctype = 'Rent Management Settings'")
	)
	for field, value in DEFAULTS.items():
		if field not in saved:
			frappe.db.set_single_value("Rent Management Settings", field, value)
