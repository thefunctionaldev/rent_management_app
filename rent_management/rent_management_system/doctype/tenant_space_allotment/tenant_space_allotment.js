// Copyright (c) 2026, Shashank Dixit and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tenant Space Allotment", {
	setup(frm) {
		frm.set_query("room", () => ({
			filters: { status: ["in", ["Available", "Partly Occupied", "Reserved"]] },
		}));
	},

	onload(frm) {
		if (!frm.is_new()) return;
		// agreement terms default to the ones in Rent Management Settings
		frappe.db.get_doc("Rent Management Settings").then((settings) => {
			const defaults = {
				agreement_months: settings.default_agreement_months,
				lock_in_months: settings.default_lock_in_months,
				notice_period_days: settings.default_notice_days,
				rent_increase_percent: settings.default_rent_increase_percent,
			};
			for (const [field, value] of Object.entries(defaults)) {
				if (!frm.doc[field] && value) frm.set_value(field, value);
			}
		});
	},

	refresh(frm) {
		if (
			frm.doc.status === "Vacated" &&
			frm.doc.security_deposit > 0 &&
			frm.doc.deposit_collected &&
			!frm.doc.deposit_settlement
		) {
			frm.add_custom_button(
				__("Deposit Settlement"),
				() => {
					frappe.new_doc("Security Deposit Settlement", {
						tenant_space_allotment: frm.doc.name,
					});
				},
				__("Create")
			);
		}

		if (frm.doc.docstatus !== 1 || frm.doc.status !== "Active") return;

		frm.add_custom_button(
			__("Rent Invoice"),
			() => {
				frappe.new_doc("Tenant Rent Invoice", {
					tenant_space_allotment: frm.doc.name,
				});
			},
			__("Create")
		);

		frm.add_custom_button(__("Vacate"), () => {
			frappe.prompt(
				{
					fieldname: "vacate_date",
					fieldtype: "Date",
					label: __("Vacate Date"),
					default: frappe.datetime.get_today(),
					reqd: 1,
				},
				(values) => {
					frm.call("vacate", values).then(() => frm.reload_doc());
				},
				__("Vacate Room {0}", [frm.doc.room]),
				__("Vacate")
			);
		});
	},
});
