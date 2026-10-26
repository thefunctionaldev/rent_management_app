# Copyright (c) 2026, Shashank Dixit and contributors
# For license information, please see license.txt

"""Bench commands to run the SaaS:

bench --site <site> rent-subscription                       # show status
bench --site <site> rent-subscription --plan growth --cycle Yearly --amount 14990 --reference NEFT123
bench --site <site> rent-subscription --plan pro --until 2027-03-31    # free / custom deal
bench --site <site> rent-subscription --restart-trial
bench --site <site> rent-add-manager owner@example.com --first-name Ravi
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


commands = [rent_subscription, rent_add_manager]
