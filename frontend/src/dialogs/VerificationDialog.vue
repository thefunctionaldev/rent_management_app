<template>
	<Modal
		open
		title="Police verification"
		:subtitle="`${stay.tenant_name} · room ${stay.room}`"
		@close="$emit('close')"
	>
		<div class="space-y-4">
			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
				<button
					v-for="s in statuses"
					:key="s.value"
					type="button"
					class="rounded-xl px-3 py-2.5 text-sm font-medium ring-1 transition"
					:class="
						form.status === s.value
							? 'bg-brand-600 text-white ring-brand-600'
							: 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
					"
					@click="form.status = s.value"
				>
					{{ s.label }}
				</button>
			</div>

			<div
				v-if="form.status === 'Pending'"
				class="rounded-xl bg-slate-50 p-4 text-sm text-slate-600"
			>
				Print the form, have the tenant sign it, and submit it with a copy of their ID at
				the police station.
				<Button size="sm" class="mt-3" :icon="Printer" :href="formUrl" target="_blank"
					>Print the verification form</Button
				>
			</div>

			<template v-if="form.status === 'Submitted' || form.status === 'Verified'">
				<div class="grid gap-4 sm:grid-cols-2">
					<Field label="Submitted on">
						<input
							v-model="form.submitted_on"
							type="date"
							class="input"
							:max="boot.today"
						/>
					</Field>
					<Field label="Police station">
						<input v-model="form.police_station" class="input" />
					</Field>
				</div>
				<Field label="Acknowledgement no.">
					<input v-model="form.reference" class="input" />
				</Field>
				<FileInput
					v-model="form.acknowledgement"
					:current="stay.verification_acknowledgement || ''"
					placeholder="Photo of the acknowledgement"
				/>
			</template>
			<template v-if="form.status === 'Verified'">
				<Field label="Verified on">
					<input
						v-model="form.verified_on"
						type="date"
						class="input"
						:max="boot.today"
					/>
				</Field>
				<FileInput
					v-model="form.copy"
					:current="stay.verification_copy || ''"
					placeholder="The verified (stamped) copy"
				/>
			</template>
			<Field label="Note">
				<input v-model="form.note" class="input" placeholder="Called the station on…" />
			</Field>
		</div>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" :loading="loading" @click="save">Save</Button>
		</template>
	</Modal>
</template>

<script setup>
import { Printer } from "lucide-vue-next";
import { reactive } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import FileInput from "@/components/FileInput.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction } from "@/useResource";

const props = defineProps({ stay: { type: Object, required: true } });
const emit = defineEmits(["close"]);

const statuses = [
	{ value: "Pending", label: "To submit" },
	{ value: "Submitted", label: "Submitted" },
	{ value: "Verified", label: "Verified" },
	{ value: "Not Required", label: "Not needed" },
];
const s = props.stay;
const form = reactive({
	status: s.police_verification === "Pending" ? "Submitted" : s.police_verification || "Pending",
	submitted_on: s.verification_submitted_on || boot.today,
	police_station: s.police_station || "",
	reference: s.verification_reference || "",
	verified_on: s.verified_on || boot.today,
	note: s.verification_note || "",
	acknowledgement: "",
	copy: "",
});
const formUrl = `/api/method/rent_management.api.download_verification_form?allotment=${encodeURIComponent(
	s.name
)}`;

const { loading, run } = useAction(
	() =>
		post("update_verification", {
			allotment: s.name,
			data: {
				...form,
				acknowledgement: form.acknowledgement || null,
				copy: form.copy || null,
			},
		}),
	{ success: "Verification saved" }
);
async function save() {
	await run();
	emit("close");
}
</script>
