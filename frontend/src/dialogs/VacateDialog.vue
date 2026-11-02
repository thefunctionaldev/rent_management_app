<template>
	<Modal
		open
		title="Vacate room"
		:subtitle="`${tenantName} · Room ${room}`"
		width="sm"
		@close="$emit('close')"
	>
		<form id="vacate-form" class="space-y-4" @submit.prevent="save">
			<Field label="Move-out date" required>
				<input v-model="vacateDate" type="date" class="input" required />
			</Field>
			<div class="flex gap-3 rounded-xl bg-amber-50 p-3.5 text-sm text-amber-800">
				<Info class="mt-0.5 size-4 shrink-0" />
				<p>
					The room becomes available right away. The last invoice is charged only up to
					the move-out date, and the security deposit can then be settled from
					<b>{{ $t("Deposits") }}</b>.
				</p>
			</div>
		</form>
		<template #footer>
			<Button @click="$emit('close')">{{ $t("Cancel") }}</Button>
			<Button
				variant="danger"
				type="submit"
				form="vacate-form"
				:loading="loading"
				:icon="LogOut"
			>
				Vacate
			</Button>
		</template>
	</Modal>
</template>

<script setup>
import { Info, LogOut } from "lucide-vue-next";
import { ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction } from "@/useResource";

const props = defineProps({
	allotment: { type: String, required: true },
	room: { type: String, default: "" },
	tenantName: { type: String, default: "" },
});
const emit = defineEmits(["close"]);
const vacateDate = ref(boot.today);

const { loading, run } = useAction(
	() => post("vacate_room", { allotment: props.allotment, vacate_date: vacateDate.value }),
	{ success: `Room ${props.room} is now available` }
);

async function save() {
	await run();
	emit("close");
}
</script>
