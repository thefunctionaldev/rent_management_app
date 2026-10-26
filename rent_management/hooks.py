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
website_route_rules = [{"from_route": "/rent/<path:app_path>", "to_route": "rent"}]

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
doc_events["Rent Payment"]["on_submit"] = "rent_management.notifications.on_payment_submit"
doc_events["User"] = {"validate": "rent_management.subscription.check_user_limit"}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"rent_management.rent_management_system.billing.mark_overdue_invoices",
		"rent_management.subscription.daily",
		"rent_management.rent_collection.reconcile_payment_links",
		"rent_management.notifications.send_due_reminders",
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
