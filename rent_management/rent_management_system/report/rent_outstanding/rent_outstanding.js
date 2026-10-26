// Copyright (c) 2026, Shashank Dixit and contributors
// For license information, please see license.txt

frappe.query_reports["Rent Outstanding"] = {
	filters: [
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "property",
			label: __("Building"),
			fieldtype: "Link",
			options: "Rent Property",
		},
		{
			fieldname: "tenant",
			label: __("Tenant"),
			fieldtype: "Link",
			options: "Tenant",
		},
		{
			fieldname: "room",
			label: __("Room"),
			fieldtype: "Link",
			options: "Tenant Space",
		},
		{
			fieldname: "overdue_only",
			label: __("Overdue Only"),
			fieldtype: "Check",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_overdue" && data && data.days_overdue > 0) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
