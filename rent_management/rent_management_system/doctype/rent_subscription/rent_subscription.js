// Copyright (c) 2026, Shashank Dixit and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rent Subscription", {
	refresh(frm) {
		frm.add_custom_button(__("Manage Subscription"), () => {
			window.location.href = "/rent/billing";
		});
	},
});
