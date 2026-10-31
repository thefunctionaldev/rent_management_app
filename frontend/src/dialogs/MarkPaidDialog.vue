<template>
	<Modal
		open
		title="Mark bills paid"
		:subtitle="`${invoices.length} bill${invoices.length === 1 ? '' : 's'} · ${money(total)}`"
		width="sm"
		@close="$emit('close')"
	>
		<form v-if="!result" id="mark-paid-form" class="space-y-4" @submit.prevent="save">
			<p class="text-sm text-slate-500">
				Each bill's balance is recorded as paid, with these details.
			</p>
			<div class="grid grid-cols-2 gap-4">
				<Field label="Paid by" required>
					<select v-model="form.mode_of_payment" class="input">
						<option v-for="m in modes" :key="m">{{ m }}</option>
					</select>
				</Field>
				<Field label="Paid on" required>
					<input
						v-model="form.payment_date"
						type="date"
						class="input"
						:max="boot.today"
						required
					/>
				</Field>
			</div>
			<Field v-if="invoices.length === 1" label="Reference (UTR)">
				<input v-model="form.reference_no" class="input" />
			</Field>
		</form>
		<div v-else class="space-y-3 py-2 text-sm">
			<p class="text-lg font-semibold">
				{{ result.paid }} bill{{ result.paid === 1 ? "" : "s" }} marked paid ·
				{{ money(result.amount) }}
			</p>
			<div v-if="result.failed.length" class="rounded-xl bg-rose-50 p-3 text-rose-800">
				<p v-for="(f, i) in result.failed" :key="i">{{ f.tenant_name }}: {{ f.why }}</p>
			</div>
		</div>
		<template #footer>
			<template v-if="!result">
				<Button @click="$emit('close')">Cancel</Button>
				<Button variant="primary" type="submit" form="mark-paid-form" :loading="saving"
					>Mark paid</Button
				>
			</template>
			<Button v-else variant="primary" @click="$emit('close')">Done</Button>
		</template>
	</Modal>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot, bumpData, toast } from "@/store";
import { money } from "@/utils";

const props = defineProps({ invoices: { type: Array, required: true } }); // [{ name, outstanding_amount }]
defineEmits(["close"]);

const modes = ["Cash", "UPI", "Bank Transfer", "Cheque", "Card", "Other"];
const form = reactive({ mode_of_payment: "Cash", payment_date: boot.today, reference_no: "" });
const total = computed(() => props.invoices.reduce((s, i) => s + i.outstanding_amount, 0));
const result = ref(null);
const saving = ref(false);

async function save() {
	saving.value = true;
	try {
		result.value = await post("mark_invoices_paid", {
			invoices: props.invoices.map((i) => i.name),
			...form,
		});
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}
</script>
