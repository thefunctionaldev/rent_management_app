# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Bench commands to run the SaaS:

bench --site <site> rent-subscription                       # show status
bench --site <site> rent-subscription --plan growth --cycle Yearly --amount 14990 --reference NEFT123
bench --site <site> rent-subscription --plan pro --until 2027-03-31    # free / custom deal
bench --site <site> rent-subscription --restart-trial
bench --site <site> rent-add-manager owner@example.com --first-name Ravi
bench --site demo.localhost rent-demo-data                  # demo data on a new site
"""

import click
from frappe.commands import get_site, pass_context


def connect(context):
	import frappe

	frappe.init(site=get_site(context))
	frappe.connect()
	return frappe


@click.command("rent-subscription")
@click.option("--plan", help="Plan key, e.g. starter / growth / pro. Records a manual payment.")
@click.option("--cycle", type=click.Choice(["Monthly", "Yearly"]), default="Monthly", show_default=True)
@click.option("--amount", type=float, default=0, help="Amount received, for your records.")
@click.option("--reference", help="Bank transfer / UPI reference, or a note.")
@click.option("--until", help="Paid-until date (YYYY-MM-DD) instead of one billing cycle.")
@click.option("--restart-trial", is_flag=True, help="Start a fresh free trial.")
@pass_context
def rent_subscription(
	context, plan=None, cycle="Monthly", amount=0, reference=None, until=None, restart_trial=False
):
	"""Show or change the subscription of a customer site."""
	frappe = connect(context)
	try:
		from frappe.utils import getdate, nowdate

		from rent_management import subscription

		frappe.set_user("Administrator")
		if restart_trial:
			subscription.start_trial(force=True)
		elif plan:
			start = end = None
			if until:
				start, end = getdate(nowdate()), getdate(until)
			payment = subscription.record_manual_payment(plan, cycle, amount, reference, start, end)
			click.echo(f"Recorded {payment.name}: {payment.plan_title} until {payment.period_end}")
		frappe.db.commit()

		state = subscription.get_state()
		click.echo(
			f"{frappe.local.site}: {state['status']} - {state['plan_title']} "
			f"({state['billing_cycle'] or 'trial'}), ends {state['ends_on']} "
			f"[{state['days_left']} days left]"
		)
		limits, usage = state["limits"], state["usage"]
		click.echo(
			f"rooms {usage['rooms']}/{limits['rooms'] or 'unlimited'}, "
			f"users {usage['users']}/{limits['users'] or 'unlimited'}"
			+ ("" if state["enforced"] else " (not enforced on this site)")
		)
	finally:
		frappe.destroy()


@click.command("rent-add-manager")
@click.argument("email")
@click.option("--first-name", default="Manager", show_default=True)
@click.option("--last-name", default="")
@click.option("--no-welcome-email", is_flag=True, help="Don't email the password-setup link.")
@pass_context
def rent_add_manager(context, email, first_name="Manager", last_name="", no_welcome_email=False):
	"""Create a customer login with the Rent Manager role (never give customers System Manager)."""
	frappe = connect(context)
	try:
		frappe.set_user("Administrator")
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first_name,
					"last_name": last_name,
					"send_welcome_email": 0 if no_welcome_email else 1,
				}
			)
			user.insert()
		user.add_roles("Rent Manager")
		frappe.db.commit()
		click.echo(f"{email} can now log in at {frappe.utils.get_url('/rent')}")
	finally:
		frappe.destroy()


@click.command("rent-backup-all")
@click.option("--with-files", is_flag=True, help="Include uploaded files (Aadhaar scans, bills...).")
@click.option(
	"--remote", help="rclone remote to copy backups to, e.g. b2:my-bucket/rent. Default: rent_backup_remote."
)
@click.option(
	"--keep-days", type=int, default=7, show_default=True, help="Local backups older than this are removed."
)
def rent_backup_all(with_files=False, remote=None, keep_days=7):
	"""Back up every site on this bench, and copy the backups off the server with rclone.

	Schedule it from cron, e.g. every night at 2 am:
	0 2 * * * cd /home/frappe/frappe-bench && bench rent-backup-all --with-files >> logs/rent-backup.log 2>&1
	"""
	import shutil
	import subprocess

	import frappe
	from frappe.utils import get_sites
	from frappe.utils.backups import new_backup

	failed = []
	for site in get_sites():
		frappe.init(site=site)
		frappe.connect()
		try:
			odb = new_backup(
				older_than=keep_days * 24, ignore_files=not with_files, compress=True, force=True
			)
			target = remote or frappe.conf.get("rent_backup_remote")
			click.echo(f"{site}: {odb.backup_path_db}")
			if target:
				if not shutil.which("rclone"):
					raise click.ClickException("rclone is not installed (https://rclone.org/install/)")
				backup_dir = frappe.utils.get_site_path("private", "backups")
				subprocess.run(
					["rclone", "copy", backup_dir, f"{target.rstrip('/')}/{site}", "--max-age", "48h"],
					check=True,
				)
				click.echo(f"{site}: copied to {target}/{site}")
		except Exception as e:
			failed.append(site)
			click.echo(f"{site}: backup FAILED: {e}", err=True)
		finally:
			frappe.destroy()
	if failed:
		raise click.ClickException(f"Backups failed for {', '.join(failed)}")


@click.command("rent-onboard")
@click.option("--email", required=True, help="The customer's login (Rent Manager).")
@click.option("--full-name", default="Manager", show_default=True)
@click.option("--business", help="Business name, for invoices and the first building.")
@click.option("--phone")
@click.option("--city")
@click.option("--invoice-prefix", help="Prefix of your GST invoice numbers for this customer, e.g. SHARMA.")
@click.option("--host-name", help="The site's public URL, e.g. https://sharma.rentapp.in")
@pass_context
def rent_onboard(
	context,
	email,
	full_name="Manager",
	business=None,
	phone=None,
	city=None,
	invoice_prefix=None,
	host_name=None,
):
	"""Set up a new customer site. Prints JSON with the set-password link on the last line."""
	import json

	frappe = connect(context)
	try:
		from rent_management.onboarding import onboard

		frappe.set_user("Administrator")
		result = onboard(email, full_name, business, phone, city, invoice_prefix, host_name)
		frappe.db.commit()
		click.echo(json.dumps(result))
	finally:
		frappe.destroy()


@click.command("rent-demo-data")
@click.option("--password", default="demo@1234", show_default=True, help="Password of the demo logins.")
@pass_context
def rent_demo_data(context, password="demo@1234"):
	"""Fill a new, empty site with demo data: 3 buildings, tenants and 6 months of history."""
	frappe = connect(context)
	try:
		from rent_management.demo import make_demo_data

		frappe.set_user("Administrator")
		summary = make_demo_data(password)
		frappe.db.commit()
		click.echo(
			f"Made {summary['buildings']} buildings, {summary['rooms']} rooms, {summary['tenants']} tenants, "
			f"{summary['invoices']} invoices and {summary['payments']} payments."
		)
		click.echo(f"Manager app: {frappe.utils.get_url('/rent')}  {summary['manager_login']} / {password}")
		click.echo(f"Tenant app:  {frappe.utils.get_url('/tenant')}  {summary['tenant_login']} / {password}")
		click.echo("Administrator can see everything too.")
	finally:
		frappe.destroy()


commands = [rent_subscription, rent_add_manager, rent_backup_all, rent_onboard, rent_demo_data]
