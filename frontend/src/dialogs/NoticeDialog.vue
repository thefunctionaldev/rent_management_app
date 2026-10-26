<template>
	<Modal
		open
		title="Give notice"
		:subtitle="`${tenantName} · Room ${allotment.room}`"
		@close="$emit('close')"
	>
		<form id="notice-form" class="space-y-4" @submit.prevent="save">
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Notice given on" required>
					<input v-model="form.notice_date" type="date" class="input" required />
				</Field>
				<Field
					label="Moving out on"
					:hint="`Notice period: ${allotment.notice_period_days || 0} days`"
				>
					<input
						v-model="form.vacate_date"
						type="date"
						class="input"
						:min="form.notice_date"
					/>
				</Field>
			</div>
			<p v-if="inLockIn" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
				The lock-in runs until {{ date(lockInEnds) }}. Moving out earlier breaks the
				agreement.
			</p>
			<p class="text-sm text-slate-500">
				The tenant stays until you mark them as vacated. Until then they show under "Moving
				out soon" on the dashboard.
			</p>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="notice-form" :loading="loading"
				>Save notice</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { computed, reactive, watch } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction } from "@/useResource";
import { date } from "@/utils";

const props = defineProps({
	allotment: { type: Object, required: true },
	tenantName: { type: String, default: "" },
});
const emit = defineEmits(["close"]);

const addDays = (value, days) => {
	const d = new Date(`${value}T00:00:00`);
	d.setDate(d.getDate() + days);
	return d.toISOString().slice(0, 10);
};
const addMonths = (value, months) => {
	const d = new Date(`${value}T00:00:00`);
	d.setMonth(d.getMonth() + months);
	return d.toISOString().slice(0, 10);
};

const form = reactive({ notice_date: boot.today, vacate_date: "" });
watch(
	() => form.notice_date,
	(value) =>
		value && (form.vacate_date = addDays(value, props.allotment.notice_period_days || 0)),
	{ immediate: true }
);
const lockInEnds = computed(() =>
	props.allotment.lock_in_months
		? addMonths(props.allotment.allotment_date, props.allotment.lock_in_months)
		: null
);
const inLockIn = computed(() => lockInEnds.value && form.vacate_date < lockInEnds.value);

const { loading, run } = useAction(
	() => post("give_notice", { allotment: props.allotment.name, ...form }),
	{ success: "Notice saved" }
);
async function save() {
	await run();
	emit("close");
}
</script>
