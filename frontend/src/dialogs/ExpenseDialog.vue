<template>
	<Modal
		open
		:title="expense ? 'Edit expense' : 'Add expense'"
		subtitle="Money spent running a building"
		@close="$emit('close')"
	>
		<form id="expense-form" class="space-y-4" @submit.prevent="save">
			<div class="grid gap-4 sm:grid-cols-2">
				<Field v-if="buildings.length > 1" label="Building" required>
					<select v-model="form.property" class="input" required>
						<option v-for="b in buildings" :key="b.name" :value="b.name">
							{{ b.name }}
						</option>
					</select>
				</Field>
				<Field label="Category" required>
					<select v-model="form.category" class="input" required>
						<option v-for="c in categories" :key="c">{{ c }}</option>
					</select>
				</Field>
				<Field label="Amount" required>
					<input
						v-model.number="form.amount"
						type="number"
						min="1"
						step="0.01"
						class="input tabular"
						required
						autofocus
					/>
				</Field>
				<Field label="Date" required>
					<input v-model="form.expense_date" type="date" class="input" required />
				</Field>
				<Field label="Paid to">
					<input
						v-model="form.paid_to"
						class="input"
						placeholder="MSEB, plumber, staff name..."
					/>
				</Field>
				<Field label="Paid by">
					<select v-model="form.mode_of_payment" class="input">
						<option v-for="m in modes" :key="m">{{ m }}</option>
					</select>
				</Field>
				<Field label="Reference no">
					<input v-model="form.reference_no" class="input" />
				</Field>
			</div>
			<Field label="Notes">
				<textarea v-model="form.description" class="input" rows="2" />
			</Field>
		</form>
		<template #footer>
			<Button
				v-if="expense"
				variant="ghost"
				class="sm:mr-auto"
				:loading="removing.loading.value"
				@click="remove"
				>Delete</Button
			>
			<Button @click="$emit('close')">Cancel</Button>
			<Button
				variant="primary"
				type="submit"
				form="expense-form"
				:loading="saving.loading.value"
				>{{ expense ? "Save" : "Add expense" }}</Button
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
import { activeProperties, boot, ui } from "@/store";
import { useAction } from "@/useResource";

const props = defineProps({
	expense: { type: Object, default: null },
	categories: { type: Array, default: () => ["Other"] },
});
const emit = defineEmits(["close"]);
const modes = ["Cash", "UPI", "Bank Transfer", "Cheque", "Card", "Other"];
const buildings = computed(() => activeProperties());

const e = props.expense || {};
const form = reactive({
	property: e.property || ui.property || buildings.value[0]?.name || "",
	category: e.category || props.categories[0],
	amount: e.amount || "",
	expense_date: e.expense_date || boot.today,
	paid_to: e.paid_to || "",
	mode_of_payment: e.mode_of_payment || "Cash",
	reference_no: e.reference_no || "",
	description: e.description || "",
});

const saving = useAction(
	() => post("save_expense", { data: { ...form, name: props.expense?.name } }),
	{
		success: props.expense ? "Expense saved" : "Expense added",
	}
);
const removing = useAction(() => post("delete_expense", { name: props.expense.name }), {
	success: "Expense deleted",
});
async function save() {
	await saving.run();
	emit("close");
}
async function remove() {
	await removing.run();
	emit("close");
}
</script>
