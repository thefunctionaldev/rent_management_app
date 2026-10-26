// Copyright (c) 2026, Shashank Dixit and contributors
// For license information, please see license.txt

const isMasked = (value) => /^\*+$/.test(value || "");

frappe.ui.form.on("Tenant", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.aadhar_last4) return;
		frm.add_custom_button(__("Show Aadhaar"), () => {
			frappe.call("rent_management.api.reveal_aadhaar", { name: frm.doc.name }).then((r) => {
				frappe.msgprint({
					title: __("Aadhaar Number"),
					message: `<p class="text-lg">${frappe.utils.escape_html(r.message)}</p>
							<p class="text-muted small">${__("This view has been logged.")}</p>`,
				});
				frm.reload_doc();
			});
		});
	},

	aadhar_card_number(frm) {
		const aadhar = (frm.doc.aadhar_card_number || "").replace(/\s/g, "");
		if (!aadhar || isMasked(aadhar)) return;

		// instant first digit check
		if (["0", "1"].includes(aadhar[0])) {
			frm.set_value("aadhar_card_number", "");
			frappe.msgprint(__("Invalid Aadhaar: Cannot start with 0 or 1."));
		}
		if (aadhar.length > 12) {
			frappe.msgprint(__("Aadhaar cannot exceed 12 digits."));
			frm.set_value("aadhar_card_number", aadhar.substring(0, 12));
		}
	},

	validate(frm) {
		const aadhar = (frm.doc.aadhar_card_number || "").replace(/\s/g, "");
		if (aadhar && !isMasked(aadhar) && aadhar.length !== 12) {
			frappe.msgprint(__("Final Check: Aadhaar must be exactly 12 digits."));
			frappe.validated = false; // stops the save
		}
	},
});
