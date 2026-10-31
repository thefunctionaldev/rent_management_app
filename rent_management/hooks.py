app_name = "rent_management"
app_title = "Rent Management System"
app_publisher = "Shashank Dixit"
app_description = "Rent Management System"
app_email = "dshashank477@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "rent_management",
# 		"logo": "/assets/rent_management/logo.png",
# 		"title": "Rent Management System",
# 		"route": "/rent_management",
# 		"has_permission": "rent_management.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/rent_management/css/rent_management.css"
# app_include_js = "/assets/rent_management/js/rent_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/rent_management/css/rent_management.css"
# web_include_js = "/assets/rent_management/js/rent_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "rent_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "rent_management/public/icons.svg"

# Frontend (Vue app in /frontend, served at /rent)
website_route_rules = [
	{"from_route": "/rent/<path:app_path>", "to_route": "rent"},
	{"from_route": "/tenant/<path:app_path>", "to_route": "tenant"},
	{"from_route": "/stay/<path:building>", "to_route": "stay"},  # the public listing page
]

# the apps' manifests and service workers (/rent/sw.js...), see rent_management/pwa.py
page_renderer = ["rent_management.pwa.AppFilesRenderer"]

# tenants (website users) land in the tenant app after logging in, staff logins in the manager app
role_home_page = {"Rent Tenant": "tenant", "Rent Staff": "rent"}

# staff logins only see the records of their areas and building, see rent_management/access.py
_staff_doctypes = (
	"Tenant", "Tenant Space Allotment", "Tenant Space", "Room Inspection", "Tenant Check-in",
	"Tenant Rent Invoice", "Rent Payment", "Night Attendance", "Tenant Leave", "Visitor Log", "Meal Opt-out",
	"Mess Menu", "Maintenance Request", "Rent Lead", "Meter Reading", "Property Expense", "Rent Notice",
	"Cash Handover", "Tenant Document",
)  # fmt: skip
has_permission = {doctype: "rent_management.access.has_permission" for doctype in _staff_doctypes}
permission_query_conditions = {
	doctype: "rent_management.access.query_conditions" for doctype in _staff_doctypes
}

add_to_apps_screen = [
	{
		"name": "rent_management",
		"logo": "/assets/rent_management/frontend/favicon.svg",
		"title": "Rent Management",
		"route": "/rent",
		"has_permission": "rent_management.api.has_app_permission",
	}
]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "rent_management.utils.jinja_methods",
# 	"filters": "rent_management.utils.jinja_filters"
# }
jinja = {
	"methods": [
		"rent_management.gst.get_rent_vendor",
		"rent_management.rent_collection.get_rent_payment_options",
		"rent_management.rent_management_system.doctype.tenant_space_allotment.tenant_space_allotment.get_agreement_context",
		"rent_management.checkin.get_verification_context",
	]
}

# Installation
# ------------

# before_install = "rent_management.install.before_install"
# after_install = "rent_management.install.after_install"
after_install = "rent_management.subscription.after_install"

# Uninstallation
# ------------

# before_uninstall = "rent_management.uninstall.before_uninstall"
# after_uninstall = "rent_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "rent_management.utils.before_app_install"
# after_app_install = "rent_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "rent_management.utils.before_app_uninstall"
# after_app_uninstall = "rent_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rent_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# a lapsed subscription makes the app read-only, see rent_management/subscription.py
_subscription_check = {
	"validate": "rent_management.subscription.check_writable",
	"before_cancel": "rent_management.subscription.check_writable",
	"on_trash": "rent_management.subscription.check_writable",
}
doc_events = {
	doctype: dict(_subscription_check)
	for doctype in (
		"Rent Property",
		"Tenant",
		"Tenant Space Type",
		"Tenant Space",
		"Tenant Space Allotment",
		"Tenant Rent Invoice",
		"Rent Payment",
		"Security Deposit Settlement",
		"Rent Management Settings",
		"Meter Reading",
		"Property Expense",
		"Rent Lead",
		"Room Inspection",
		"Meal Opt-out",
		"Mess Menu",
		"Tenant Leave",
		"Visitor Log",
		"Night Attendance",
		"Staff Member",
		"Staff Advance",
		"Salary Slip",
		"Rent Referral",
		"Rent Notice",
		"Cash Handover",
		"Tenant Document",
		"Bank Statement",
	)
}
doc_events["Tenant Space"]["validate"] = [
	"rent_management.subscription.check_writable",
	"rent_management.subscription.check_bed_limit",
]
doc_events["Rent Property"]["validate"] = [
	"rent_management.subscription.check_writable",
	"rent_management.subscription.check_property_limit",
]
doc_events["Rent Payment"]["on_submit"] = [
	"rent_management.notifications.on_payment_submit",
	"rent_management.referrals.on_payment",
]
doc_events["Rent Payment"]["on_cancel"] = "rent_management.referrals.on_payment"
# who holds the cash, for the cash book (rent_management/cash.py)
doc_events["Rent Payment"]["before_submit"] = "rent_management.cash.set_collected_by"
doc_events["Property Expense"]["validate"] = [
	"rent_management.subscription.check_writable",
	"rent_management.cash.set_paid_by",
]
# referral credits on rent invoices, see rent_management/referrals.py
doc_events["Tenant Rent Invoice"].update(
	{
		"after_insert": "rent_management.referrals.link_credits",
		"on_cancel": "rent_management.referrals.release_credits",
		"on_trash": [
			"rent_management.subscription.check_writable",
			"rent_management.referrals.release_credits",
		],
	}
)
doc_events["Rent Lead"]["on_update"] = "rent_management.referrals.sync_lead"
doc_events["User"] = {"validate": "rent_management.subscription.check_user_limit"}
# the activity log keeps its entries when what they name is cancelled or deleted
ignore_links_on_delete = ["Rent Activity"]

# app notifications also go to managers' phones
doc_events["Notification Log"] = {"after_insert": "rent_management.pwa.on_notification"}


# the activity log for owners, see rent_management/activity.py (keep in step with activity.HANDLERS)
def _also(doctype, event, method):
	events = doc_events.setdefault(doctype, {})
	current = events.get(event)
	events[event] = [*([current] if isinstance(current, str) else current or []), method]


for _doctype, _event in (
	("Rent Payment", "on_submit"),
	("Rent Payment", "on_cancel"),
	("Rent Payment", "on_trash"),
	("Tenant Rent Invoice", "on_submit"),
	("Tenant Rent Invoice", "on_cancel"),
	("Tenant Rent Invoice", "on_trash"),
	("Tenant Space Allotment", "on_submit"),
	("Tenant Space Allotment", "on_update_after_submit"),
	("Security Deposit Settlement", "on_submit"),
	("Security Deposit Settlement", "on_cancel"),
	("Property Expense", "after_insert"),
	("Property Expense", "on_update"),
	("Property Expense", "on_trash"),
	("Salary Slip", "on_update"),
	("Staff Advance", "after_insert"),
	("Tenant Leave", "on_update"),
	("Cash Handover", "after_insert"),
	("Cash Handover", "on_update"),
	("Tenant", "after_insert"),
	("Tenant", "on_trash"),
	("Rent Management Settings", "on_update"),
	("Rent Notice", "on_trash"),
):
	_also(_doctype, _event, "rent_management.activity.on_event")

# PANs on rent receipts look right, see rent_management/receipts.py
_also("Rent Management Settings", "validate", "rent_management.receipts.check_pan")
_also("Rent Property", "validate", "rent_management.receipts.check_pan")
# new stays to verify with the police, see rent_management/verification.py
_also("Tenant Space Allotment", "on_submit", "rent_management.verification.on_move_in")
# moving out in the tenant app
_also("Room Inspection", "on_update", "rent_management.move_out.on_checklist_update")
_also("Security Deposit Settlement", "on_submit", "rent_management.move_out.on_settlement_submit")

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"rent_management.rent_management_system.billing.mark_overdue_invoices",
		"rent_management.subscription.daily",
		"rent_management.rent_collection.reconcile_payment_links",
		"rent_management.leads.reconcile_token_links",
		"rent_management.salaries.remind_due",
		"rent_management.fees.apply_late_fees",
		"rent_management.owner_summary.send_monthly",
		"rent_management.verification.remind",
		"rent_management.documents.remind_expiring",
		"rent_management.move_out.remind",
		"rent_management.notifications.send_due_reminders",
		"rent_management.saas.send_heartbeat",
		"rent_management.rent_management_system.doctype.tenant_space_allotment.tenant_space_allotment.apply_rent_increases",
	],
	"monthly": ["rent_management.rent_management_system.billing.generate_monthly_invoices"],
}

# scheduler_events = {
# 	"all": [
# 		"rent_management.tasks.all"
# 	],
# 	"daily": [
# 		"rent_management.tasks.daily"
# 	],
# 	"hourly": [
# 		"rent_management.tasks.hourly"
# 	],
# 	"weekly": [
# 		"rent_management.tasks.weekly"
# 	],
# 	"monthly": [
# 		"rent_management.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "rent_management.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "rent_management.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "rent_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "rent_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["rent_management.utils.before_request"]
# after_request = ["rent_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["rent_management.utils.before_job"]
# after_job = ["rent_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"rent_management.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
