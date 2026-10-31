<template>
	<Modal
		open
		title="Generate monthly invoices"
		subtitle="One invoice for every tenant who stayed during the month"
		width="sm"
		@close="$emit('close')"
	>
		<form v-if="!result" id="generate-form" class="space-y-4" @submit.prevent="save">
			<div class="grid grid-cols-2 gap-4">
				<Field label="Month" required>
					<select v-model="form.billing_month" class="input">
						<option v-for="m in boot.months" :key="m">{{ m }}</option>
					</select>
				</Field>
				<Field label="Year" required>
					<input
						v-model="form.billing_year"
						type="number"
						class="input tabular"
						required
					/>
				</Field>
			</div>
			<Field v-if="activeProperties().length > 1" label="Building">
				<select v-model="form.property" class="input">
					<option value="">All buildings</option>
					<option v-for="b in activeProperties()" :key="b.name" :value="b.name">
						{{ b.name }}
					</option>
				</select>
			</Field>
			<label class="flex items-center gap-2 text-sm text-slate-700">
				<input v-model="form.submit" type="checkbox" class="size-4 accent-brand-600" />
				Submit invoices right away
			</label>
			<p class="text-xs text-slate-500">
				Tenants who already have an invoice for this month are skipped.
			</p>
		</form>
		<div v-else class="py-4 text-center">
			<span
				class="mx-auto grid size-12 place-items-center rounded-full bg-emerald-50 text-emerald-600"
			>
				<CircleCheck class="size-6" />
			</span>
			<p class="mt-3 text-lg font-semibold">
				{{ result.length }} invoice{{ result.length === 1 ? "" : "s" }} created
			</p>
			<p class="mt-1 text-sm text-slate-500">
				for {{ form.billing_month }} {{ form.billing_year }}
			</p>
		</div>
		<template #footer>
			<template v-if="!result">
				<Button @click="$emit('close')">Cancel</Button>
				<Button
					variant="primary"
					type="submit"
					form="generate-form"
					:loading="loading"
					:icon="Sparkles"
					>Generate</Button
				>
			</template>
			<Button v-else variant="primary" @click="$emit('close')">Done</Button>
		</template>
	</Modal>
</template>

<script setup>
import { CircleCheck, Sparkles } from "lucide-vue-next";
import { reactive, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { activeProperties, boot, ui } from "@/store";
import { useAction } from "@/useResource";
import { currentMonth } from "@/utils";

defineEmits(["close"]);
const { month, year } = currentMonth();
const form = reactive({
	billing_month: month,
	billing_year: year,
	submit: false,
	property: ui.property || "",
});
const result = ref(null);

const { loading, run } = useAction(() =>
	post("generate_invoices", { ...form, submit: form.submit ? 1 : 0 })
);

async function save() {
	result.value = (await run()).created;
}
</script>
