<template>
	<Modal
		open
		title="Meal plan"
		:subtitle="`${stay.tenant_name} · Room ${stay.room}`"
		@close="$emit('close')"
	>
		<form id="meal-plan-form" class="space-y-4" @submit.prevent="save">
			<div class="grid gap-2">
				<label
					v-for="p in plans"
					:key="p.value"
					class="flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm"
					:class="
						form.meal_plan === p.value
							? 'border-brand-500 bg-brand-50/50'
							: 'border-slate-200'
					"
				>
					<input
						v-model="form.meal_plan"
						type="radio"
						:value="p.value"
						class="mt-0.5 accent-brand-600"
					/>
					<span>
						<span class="font-medium">{{ p.label }}</span>
						<span class="block text-slate-500">{{ p.hint }}</span>
					</span>
				</label>
			</div>
			<Field v-if="form.meal_plan === 'Paid Monthly'" label="Charge per month" required>
				<input
					v-model.number="form.meal_charge"
					class="input tabular"
					type="number"
					min="1"
					required
				/>
			</Field>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="meal-plan-form" :loading="loading"
				>Save</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { reactive } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { useAction } from "@/useResource";

const props = defineProps({ stay: { type: Object, required: true } });
const emit = defineEmits(["close"]);
const plans = [
	{ value: "Included in Rent", label: "Included in the rent", hint: "Meals come with the room" },
	{
		value: "Paid Monthly",
		label: "Paid monthly",
		hint: "Added to every rent invoice, for the days stayed",
	},
	{ value: "", label: "No meals", hint: "Not counted in the kitchen" },
];
const form = reactive({
	meal_plan: props.stay.meal_plan || "",
	meal_charge: props.stay.meal_charge || "",
});
const { loading, run } = useAction(
	() => post("set_meal_plan", { allotment: props.stay.name, ...form }),
	{ success: "Meal plan saved" }
);
async function save() {
	await run();
	emit("close");
}
</script>
