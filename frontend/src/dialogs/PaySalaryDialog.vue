<template>
	<Modal
		open
		:title="`Pay ${slip.staff_name}`"
		:subtitle="`${slip.salary_month || month} salary`"
		@close="$emit('close')"
	>
		<form id="pay-salary-form" class="space-y-4" @submit.prevent="save">
			<div class="rounded-xl bg-slate-50 p-4 text-center">
				<p class="text-sm text-slate-500">Net pay</p>
				<p class="tabular text-3xl font-semibold">{{ money(slip.net_pay) }}</p>
				<p v-if="payTo" class="mt-1 text-sm text-slate-600">{{ payTo }}</p>
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Paid on" required>
					<input v-model="form.paid_on" class="input" type="date" required />
				</Field>
				<Field label="Paid by">
					<select v-model="form.mode_of_payment" class="input">
						<option v-for="m in modes" :key="m">{{ m }}</option>
					</select>
				</Field>
			</div>
			<Field label="Reference no" hint="UTR or cheque number">
				<input v-model="form.reference_no" class="input" />
			</Field>
			<p class="text-xs text-slate-500">
				It's recorded as a Salaries expense of {{ slip.property }}.
			</p>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="pay-salary-form" :loading="loading"
				>Mark paid</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { computed, reactive } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction } from "@/useResource";
import { money } from "@/utils";

const props = defineProps({
	slip: { type: Object, required: true },
	month: { type: String, default: "" },
});
const emit = defineEmits(["close"]);

const modes = ["UPI", "Bank Transfer", "Cash", "Cheque", "Other"];
const details = props.slip.staff_details || {};
const form = reactive({
	name: props.slip.name,
	paid_on: boot.today,
	mode_of_payment: details.payment_mode || "UPI",
	reference_no: "",
});
const payTo = computed(() => {
	if (form.mode_of_payment === "UPI" && details.upi_id) return `UPI: ${details.upi_id}`;
	if (form.mode_of_payment === "Bank Transfer" && details.bank_account_no)
		return `A/c ${details.bank_account_no}${
			details.ifsc_code ? ` · ${details.ifsc_code}` : ""
		}`;
	return "";
});

const { loading, run } = useAction(() => post("pay_salary", form), {
	success: `${props.slip.staff_name}'s salary paid`,
});
async function save() {
	await run();
	emit("close");
}
</script>
