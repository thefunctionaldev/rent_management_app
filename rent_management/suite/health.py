import frappe
from frappe import _
from frappe.utils import add_days, now_datetime, nowdate

from rent_management import subscription
from rent_management.suite.common import admin, manager, save

JOBS = {
	"monthly-invoices": "rent_management.rent_management_system.billing.generate_monthly_invoices",
	"rent-reminders": "rent_management.notifications.send_due_reminders",
	"payment-sync": "rent_management.rent_collection.reconcile_payment_links",
	"recurring-bills": "rent_management.suite.recurring.generate",
	"housekeeping": "rent_management.suite.housekeeping.generate",
	"waitlist-expiry": "rent_management.suite.waitlist.expire",
	"erp-sync": "rent_management.suite.erp_sync.process_queue",
}


def run(key):
	if key not in JOBS:
		frappe.throw(_("Unknown operational job."))
	# A site-scoped lock prevents a manual retry from overlapping the scheduler.
	with frappe.cache.lock(f"rent-suite-job:{frappe.local.site}:{key}", timeout=1800, blocking_timeout=1):
		doc = save(
			frappe.get_doc(
				{
					"doctype": "Rent Job Run",
					"job_key": key,
					"status": "Running",
					"started_on": now_datetime(),
					"requested_by": frappe.session.user,
				}
			)
		)
		frappe.db.commit()
		frappe.db.savepoint("rent_suite_job")
		previous_count = getattr(frappe.local, "rent_suite_failures", None)
		frappe.local.rent_suite_failures = 0
		try:
			if subscription.skip_if_lapsed():
				doc.summary = "Subscription is read-only; no changes made."
			else:
				frappe.get_attr(JOBS[key])()
				doc.summary = "Job finished. Check individual message and sync failures below."
			doc.status = "Success"
			if frappe.local.rent_suite_failures:
				doc.status = "Partial Failure"
				doc.summary = f"{frappe.local.rent_suite_failures} items failed; successful items were retained. Review message/sync rows and the Error Log before retrying."
		except Exception:
			frappe.db.rollback(save_point="rent_suite_job")
			doc.status = "Failed"
			error = frappe.log_error(title=f"Rent job failed: {key}")
			doc.error_id = getattr(error, "name", None)
			doc.summary = "Job failed. System Managers can inspect the Error Log."
		finally:
			frappe.local.rent_suite_failures = previous_count
		doc.finished_on = now_datetime()
		save(doc)
		frappe.db.commit()


def monthly_invoices():
	run("monthly-invoices")


def reminders():
	run("rent-reminders")


def payments():
	run("payment-sync")


def daily():
	for key in ("recurring-bills", "housekeeping", "waitlist-expiry", "erp-sync"):
		run(key)
	missed_tasks()


def missed_tasks():
	if subscription.skip_if_lapsed():
		return
	for task in frappe.get_all(
		"Rent Housekeeping Task",
		filters={"status": "Open", "due_date": ["<", nowdate()]},
		fields=["name", "assigned_to", "title"],
		limit_page_length=500,
	):
		if not task.assigned_to:
			continue
		if not frappe.db.exists(
			"Notification Log",
			{
				"for_user": task.assigned_to,
				"document_type": "Rent Housekeeping Task",
				"document_name": task.name,
				"creation": [">=", nowdate()],
			},
		):
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": task.assigned_to,
					"type": "Alert",
					"subject": _("Overdue cleaning task: {0}").format(frappe.utils.escape_html(task.title)),
					"document_type": "Rent Housekeeping Task",
					"document_name": task.name,
				}
			).insert(ignore_permissions=True)


@frappe.whitelist()
def overview():
	manager()
	settings = frappe.get_single("Rent Integration Settings")
	return {
		"jobs": list(JOBS),
		"runs": frappe.get_all(
			"Rent Job Run",
			fields=["name", "job_key", "status", "started_on", "finished_on", "summary"],
			order_by="creation desc",
			limit_page_length=100,
		),
		"failed_messages": frappe.get_all(
			"Rent Message Log",
			filters={"status": "Failed", "creation": [">=", add_days(nowdate(), -30)]},
			fields=["name", "message_type", "channel", "creation", "rent_invoice"],
			order_by="creation desc",
			limit_page_length=50,
		),
		"sync_failures": frappe.db.count("Rent ERP Sync", {"status": "Failed"}),
		"overdue_tasks": frappe.db.count(
			"Rent Housekeeping Task", {"status": "Open", "due_date": ["<", nowdate()]}
		),
		"backup_at": settings.last_backup_at,
		"remote_backup_at": settings.last_remote_backup_at,
		"can_retry": "System Manager" in frappe.get_roles(),
	}


@frappe.whitelist(methods=["POST"])
def retry(key):
	admin()
	if key not in JOBS:
		frappe.throw(_("Unknown operational job."))
	frappe.enqueue(
		"rent_management.suite.health.run",
		key=key,
		queue="long",
		timeout=1800,
		job_id=f"rent-suite:{frappe.local.site}:{key}",
		deduplicate=True,
		enqueue_after_commit=True,
	)
	return {"queued": True}


def backup_success(remote=False):
	# Called only after a backup/copy actually succeeds; no optimistic timestamp.
	frappe.db.set_single_value(
		"Rent Integration Settings", "last_remote_backup_at" if remote else "last_backup_at", now_datetime()
	)
	frappe.db.commit()
