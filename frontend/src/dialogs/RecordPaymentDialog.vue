<template>
	<Modal
		open
		title="Record payment"
		:subtitle="
			selected
				? `${selected.tenant_name} · ${selected.name}`
				: 'Payment against a rent invoice'
		"
		@close="$emit('close')"
	>
		<form id="payment-form" class="space-y-5" @submit.prevent="save">
			<Field v-if="!invoice" label="Invoice" required>
				<select v-model="form.rent_invoice" class="input" required>
					<option value="" disabled>Select an unpaid invoice</option>
					<option v-for="inv in openInvoices" :key="inv.name" :value="inv.name">
						{{ inv.tenant_name }} · {{ inv.billing_month }} {{ inv.billing_year }} ·
						{{ money(inv.outstanding_amount) }} due
					</option>
				</select>
			</Field>

			<div
				v-if="selected"
				class="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3"
			>
				<div>
					<p class="text-xs text-slate-500">Outstanding</p>
					<p class="tabular text-lg font-semibold">
						{{ money(selected.outstanding_amount) }}
					</p>
				</div>
				<div class="text-right">
					<p class="text-xs text-slate-500">Room · Period</p>
					<p class="text-sm font-medium">
						{{ selected.room }} · {{ selected.billing_month }}
						{{ selected.billing_year }}
					</p>
				</div>
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Amount" required>
					<input
						v-model="form.amount"
						type="number"
						min="0"
						step="0.01"
						class="input tabular text-base font-semibold"
						required
					/>
				</Field>
				<Field label="Payment date" required>
					<input v-model="form.payment_date" type="date" class="input" required />
				</Field>
			</div>
			<p v-if="discount" class="-mt-2 text-sm text-emerald-700">
				Paid by {{ date(selected.early_discount_until) }}: {{ money(discount) }} off for
				paying early, so {{ money(selected.outstanding_amount - discount) }} settles it.
			</p>

			<div>
				<span class="label">Mode of payment</span>
				<div class="grid grid-cols-3 gap-2 sm:grid-cols-6">
					<button
						v-for="mode in modes"
						:key="mode"
						type="button"
						class="rounded-lg border px-2 py-2 text-xs font-medium transition"
						:class="
							form.mode_of_payment === mode
								? 'border-brand-500 bg-brand-50 text-brand-700 ring-2 ring-brand-100'
								: 'border-slate-200 text-slate-600 hover:bg-slate-50'
						"
						@click="form.mode_of_payment = mode"
					>
						{{ mode }}
					</button>
				</div>
			</div>
			<Field
				v-if="!['Cash', 'Other'].includes(form.mode_of_payment)"
				label="Reference number"
				required
			>
				<input
					v-model="form.reference_no"
					class="input"
					required
					placeholder="UTR / cheque / transaction id"
				/>
			</Field>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button
				variant="success"
				type="submit"
				form="payment-form"
				:loading="loading"
				:icon="Check"
				>Record payment</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { Check } from "lucide-vue-next";
import { computed, reactive, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction, useResource } from "@/useResource";
import { date, money } from "@/utils";

const props = defineProps({ invoice: { type: Object, default: null } });
const emit = defineEmits(["close"]);

const modes = ["Cash", "UPI", "Bank Transfer", "Cheque", "Card", "Other"];
const form = reactive({
	rent_invoice: props.invoice?.name || "",
	amount: "",
	payment_date: boot.today,
	mode_of_payment: "UPI",
	reference_no: "",
});

const invoices = useResource(
	() => (props.invoice ? [] : get("get_invoices", { page_length: 500 }).then((r) => r.invoices)),
	{ initial: [] }
);
const openInvoices = computed(() =>
	invoices.data.value.filter((i) => i.docstatus === 1 && i.outstanding_amount > 0)
);
const selected = computed(
	() => props.invoice || openInvoices.value.find((i) => i.name === form.rent_invoice)
);

// the early payment discount, if paid in full by its date
const discount = computed(() => {
	const inv = selected.value;
	if (!inv?.early_discount_offer || inv.late_fee || !inv.early_discount_until) return 0;
	if (form.payment_date > inv.early_discount_until) return 0;
	return Math.min(inv.early_discount_offer, inv.outstanding_amount);
});
const fullAmount = computed(() =>
	selected.value ? selected.value.outstanding_amount - discount.value : ""
);
watch(
	fullAmount,
	(amount, before) => {
		if (form.amount === "" || form.amount === before) form.amount = amount;
	},
	{ immediate: true }
);

// a payment that looks recorded already is only saved once the manager confirms it
const { loading, run } = useAction(
	async () => {
		try {
			return await post("record_payment", form);
		} catch (e) {
			if (e.type !== "DuplicatePaymentError") throw e;
			if (!window.confirm(`${e.message}\n\nRecord this one anyway?`)) return null;
			return post("record_payment", { ...form, allow_duplicate: 1 });
		}
	},
	{ success: (name) => (name ? `Payment of ${money(form.amount)} recorded` : "") }
);

async function save() {
	if (await run()) emit("close");
}
</script>
