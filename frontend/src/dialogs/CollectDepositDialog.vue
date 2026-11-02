<template>
	<Modal
		open
		title="Mark deposit collected"
		:subtitle="`${allotment.tenant_name} · Room ${allotment.room}`"
		width="sm"
		@close="$emit('close')"
	>
		<form id="collect-form" class="space-y-4" @submit.prevent="save">
			<div class="rounded-xl bg-slate-50 p-4 text-center">
				<p class="text-xs font-medium text-slate-500 uppercase">Security deposit</p>
				<p class="tabular mt-1 text-2xl font-semibold">
					{{ money(allotment.security_deposit) }}
				</p>
			</div>
			<Field label="Collected on" required>
				<input v-model="collectedOn" type="date" class="input" required />
			</Field>
		</form>
		<template #footer>
			<Button @click="$emit('close')">{{ $t("Cancel") }}</Button>
			<Button variant="primary" type="submit" form="collect-form" :loading="loading"
				>Mark collected</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction } from "@/useResource";
import { money } from "@/utils";

const props = defineProps({ allotment: { type: Object, required: true } });
const emit = defineEmits(["close"]);
const collectedOn = ref(boot.today);

const { loading, run } = useAction(
	() =>
		post("mark_deposit_collected", {
			allotment: props.allotment.name,
			collected_on: collectedOn.value,
		}),
	{ success: "Deposit marked as collected" }
);

async function save() {
	await run();
	emit("close");
}
</script>
