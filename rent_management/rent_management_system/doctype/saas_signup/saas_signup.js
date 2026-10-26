// Copyright (c) 2026, Shashank Dixit and contributors
// For license information, please see license.txt

frappe.ui.form.on("SaaS Signup", {
	refresh(frm) {
		if (["Failed", "Verified"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Provision Again"), () => {
				frappe
					.call("rent_management.signup.retry", { signup: frm.doc.name })
					.then(() => frm.reload_doc());
			});
		}
		if (frm.doc.status === "Active") {
			frm.add_custom_button(__("Open Site"), () =>
				window.open(`https://${frm.doc.site}/rent`)
			);
		}
	},
});
