<template>
	<Modal
		open
		:title="tenant ? 'Edit tenant' : 'Add tenant'"
		:subtitle="tenant ? tenant.full_name : 'Create a tenant profile'"
		width="lg"
		@close="$emit('close')"
	>
		<form id="tenant-form" class="space-y-5" @submit.prevent="save">
			<PictureInput
				v-model="picture"
				round
				:name="[form.first_name, form.last_name].filter(Boolean).join(' ')"
			/>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="First name" required>
					<input v-model="form.first_name" class="input" required autofocus />
				</Field>
				<Field label="Middle name"
					><input v-model="form.middle_name" class="input"
				/></Field>
				<Field label="Last name"><input v-model="form.last_name" class="input" /></Field>
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Mobile number">
					<input
						v-model="form.mobile_no"
						class="input"
						type="tel"
						placeholder="+91 98765 43210"
					/>
				</Field>
				<Field label="Email"
					><input v-model="form.email_id" class="input" type="email"
				/></Field>
				<Field label="Gender">
					<select v-model="form.gender" class="input">
						<option value="">—</option>
						<option>Male</option>
						<option>Female</option>
						<option>Other</option>
					</select>
				</Field>
				<Field
					label="Aadhaar number"
					:hint="
						tenant?.aadhar_last4
							? 'Saved and encrypted. Leave blank to keep it.'
							: 'Stored encrypted; only the last 4 digits are shown'
					"
				>
					<input
						v-model="form.aadhar_card_number"
						class="input tabular"
						inputmode="numeric"
						autocomplete="off"
						:placeholder="
							tenant?.aadhar_last4 ? `•••• •••• ${tenant.aadhar_last4}` : ''
						"
					/>
				</Field>
				<Field label="Date of birth"
					><input v-model="form.date_of_birth" class="input" type="date"
				/></Field>
				<Field label="Father's / guardian's name"
					><input v-model="form.guardian_name" class="input"
				/></Field>
				<Field label="Occupation"><input v-model="form.occupation" class="input" /></Field>
				<Field label="Workplace"><input v-model="form.workspace" class="input" /></Field>
				<Field label="Monthly income">
					<input v-model="form.salary" class="input tabular" type="number" min="0" />
				</Field>
				<Field v-if="tenant" label="Status">
					<select v-model="form.status" class="input">
						<option>Active</option>
						<option>Inactive</option>
					</select>
				</Field>
			</div>
			<Field label="Permanent address">
				<textarea v-model="form.permanent_address" rows="2" class="input" />
			</Field>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Emergency contact"
					><input v-model="form.emergency_contact_name" class="input" placeholder="Name"
				/></Field>
				<Field label="Relation"
					><input v-model="form.emergency_contact_relation" class="input"
				/></Field>
				<Field label="Their phone"
					><input v-model="form.emergency_contact_phone" class="input" type="tel"
				/></Field>
			</div>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="tenant-form" :loading="loading">
				{{ tenant ? "Save changes" : "Add tenant" }}
			</Button>
		</template>
	</Modal>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import PictureInput from "@/components/PictureInput.vue";
import { useAction } from "@/useResource";

const props = defineProps({ tenant: { type: Object, default: null } });
const emit = defineEmits(["close"]);
const router = useRouter();

const fields = [
	"first_name",
	"middle_name",
	"last_name",
	"mobile_no",
	"email_id",
	"gender",
	"aadhar_card_number",
	"occupation",
	"workspace",
	"salary",
	"status",
	"permanent_address",
	"date_of_birth",
	"guardian_name",
	"emergency_contact_name",
	"emergency_contact_relation",
	"emergency_contact_phone",
];
const form = reactive(Object.fromEntries(fields.map((f) => [f, props.tenant?.[f] ?? ""])));
form.aadhar_card_number = ""; // never prefilled: the saved number stays on the server
const savedPicture = props.tenant?.display_picture || "";
const picture = ref(savedPicture);

const { loading, run } = useAction((data) => post("save_tenant", { data }), {
	success: props.tenant ? "Tenant updated" : "Tenant added",
});

async function save() {
	const name = await run({
		...form,
		name: props.tenant?.name,
		salary: form.salary || 0,
		// only sent when changed: a new photo (data URL) or "" to remove it
		...(picture.value !== savedPicture && { picture: picture.value }),
	});
	emit("close");
	if (!props.tenant) router.push(`/tenants/${name}`);
}
</script>
