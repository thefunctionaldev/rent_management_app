<template>
	<Modal
		open
		title="Give an advance"
		subtitle="Recovered from their next salaries"
		@close="$emit('close')"
	>
		<form id="advance-form" class="space-y-4" @submit.prevent="save">
			<Field label="To" required>
				<select v-model="form.staff" class="input" required>
					<option value="" disabled>Choose someone</option>
					<option v-for="s in people" :key="s.name" :value="s.name">
						{{ s.staff_name }} · {{ s.role }}
					</option>
				</select>
			</Field>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Amount" required>
					<input
						v-model.number="form.amount"
						class="input tabular"
						type="number"
						min="1"
						required
					/>
				</Field>
				<Field label="Date" required>
					<input v-model="form.advance_date" class="input" type="date" required />
				</Field>
				<Field label="Recover per month" hint="empty: all from the next salary">
					<input
						v-model.number="form.recover_per_month"
						class="input tabular"
						type="number"
						min="0"
						:max="form.amount || undefined"
					/>
				</Field>
				<Field label="Paid by">
					<select v-model="form.mode_of_payment" class="input">
						<option v-for="m in modes" :key="m">{{ m }}</option>
					</select>
				</Field>
			</div>
			<Field label="Note">
				<input v-model="form.note" class="input" placeholder="Festival, medical..." />
			</Field>
			<p v-if="months" class="text-sm text-slate-500">
				Recovered over {{ months }} month{{ months === 1 ? "" : "s" }}.
			</p>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="advance-form" :loading="loading"
				>Give advance</Button
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

const props = defineProps({
	staff: { type: Array, required: true },
	selected: { type: String, default: "" },
});
const emit = defineEmits(["close"]);

const modes = ["Cash", "UPI", "Bank Transfer", "Cheque", "Other"];
const people = props.staff.filter((s) => s.is_active);
const form = reactive({
	staff: props.selected,
	amount: "",
	advance_date: boot.today,
	recover_per_month: "",
	mode_of_payment: "Cash",
	note: "",
});
const months = computed(() =>
	form.amount ? Math.ceil(form.amount / (form.recover_per_month || form.amount)) : 0
);

const { loading, run } = useAction(() => post("give_advance", form), {
	success: "Advance given",
});
async function save() {
	await run();
	emit("close");
}
</script>
