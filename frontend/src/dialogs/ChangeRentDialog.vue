<template>
	<Modal
		open
		title="Change rent"
		:subtitle="`${tenantName} · Room ${allotment.room} · now ${money(
			allotment.rent_amount
		)}/mo`"
		@close="$emit('close')"
	>
		<form id="rent-form" class="space-y-4" @submit.prevent="save">
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="New monthly rent" required>
					<input
						v-model.number="form.new_rent"
						type="number"
						min="1"
						class="input tabular"
						required
						autofocus
					/>
				</Field>
				<Field label="From" required hint="Invoices from this month use the new rent">
					<input
						v-model="form.effective_from"
						type="date"
						class="input"
						:min="allotment.allotment_date"
						required
					/>
				</Field>
			</div>
			<Field label="Reason">
				<input v-model="form.reason" class="input" placeholder="Yearly increase" />
			</Field>
			<p
				v-if="change"
				class="text-sm"
				:class="change > 0 ? 'text-slate-600' : 'text-emerald-700'"
			>
				{{ change > 0 ? "An increase" : "A reduction" }} of
				{{ money(Math.abs(change)) }} ({{
					Math.round((change / allotment.rent_amount) * 1000) / 10
				}}%).
			</p>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="rent-form" :loading="loading"
				>Change rent</Button
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
	allotment: { type: Object, required: true },
	tenantName: { type: String, default: "" },
});
const emit = defineEmits(["close"]);

const firstOfNextMonth = () => {
	const d = new Date(`${boot.today}T00:00:00`);
	return new Date(d.getFullYear(), d.getMonth() + 1, 1, 12).toISOString().slice(0, 10);
};
const form = reactive({
	new_rent: props.allotment.rent_amount,
	effective_from: firstOfNextMonth(),
	reason: "",
});
const change = computed(() => (form.new_rent || 0) - props.allotment.rent_amount);

const { loading, run } = useAction(
	() => post("revise_rent", { allotment: props.allotment.name, ...form }),
	{ success: "Rent changed" }
);
async function save() {
	await run();
	emit("close");
}
</script>
