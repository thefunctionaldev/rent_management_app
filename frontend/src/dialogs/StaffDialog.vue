<template>
	<Modal
		open
		:title="staff ? `Edit ${staff.staff_name}` : 'Add staff'"
		subtitle="Someone who works at your buildings"
		@close="$emit('close')"
	>
		<form id="staff-form" class="space-y-4" @submit.prevent="save">
			<PictureInput v-model="picture" round :name="form.staff_name" />
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Name" required>
					<input v-model="form.staff_name" class="input" required autofocus />
				</Field>
				<Field label="Role">
					<select v-model="form.role" class="input">
						<option v-for="r in roles" :key="r">{{ r }}</option>
					</select>
				</Field>
				<Field label="Works at" required>
					<select v-model="form.property" class="input" required>
						<option v-for="b in buildings" :key="b.name" :value="b.name">
							{{ b.name }}
						</option>
					</select>
				</Field>
				<Field label="Mobile">
					<input v-model="form.mobile_no" class="input" type="tel" />
				</Field>
				<Field label="Monthly salary" required>
					<input
						v-model.number="form.monthly_salary"
						class="input tabular"
						type="number"
						min="1"
						required
					/>
				</Field>
				<Field label="Paid on" hint="day of the next month">
					<input
						v-model.number="form.pay_day"
						class="input tabular"
						type="number"
						min="1"
						max="28"
					/>
				</Field>
				<Field label="Joined on" required>
					<input v-model="form.joining_date" class="input" type="date" required />
				</Field>
				<Field v-if="staff" label="Left on">
					<input
						v-model="form.leaving_date"
						class="input"
						type="date"
						:min="form.joining_date"
					/>
				</Field>
			</div>

			<div class="space-y-3 rounded-lg bg-slate-50 p-3">
				<Field label="Paid by">
					<select v-model="form.payment_mode" class="input">
						<option v-for="m in modes" :key="m">{{ m }}</option>
					</select>
				</Field>
				<Field v-if="form.payment_mode === 'UPI'" label="UPI ID">
					<input v-model="form.upi_id" class="input" placeholder="name@okaxis" />
				</Field>
				<div
					v-if="form.payment_mode === 'Bank Transfer'"
					class="grid gap-3 sm:grid-cols-2"
				>
					<Field label="Account no">
						<input v-model="form.bank_account_no" class="input tabular" />
					</Field>
					<Field label="IFSC">
						<input v-model="form.ifsc_code" class="input uppercase" />
					</Field>
				</div>
			</div>

			<details class="group">
				<summary class="cursor-pointer text-sm font-medium text-slate-700">
					Address and notes
				</summary>
				<div class="mt-3 space-y-3">
					<Field label="Address">
						<textarea v-model="form.address" class="input" rows="2" />
					</Field>
					<Field label="Emergency contact">
						<input
							v-model="form.emergency_contact"
							class="input"
							placeholder="Name and phone"
						/>
					</Field>
					<Field label="Notes">
						<textarea v-model="form.notes" class="input" rows="2" />
					</Field>
				</div>
			</details>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="staff-form" :loading="loading">{{
				staff ? "Save" : "Add staff"
			}}</Button>
		</template>
	</Modal>
</template>

<script setup>
import { reactive, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import PictureInput from "@/components/PictureInput.vue";
import { activeProperties, boot, ui } from "@/store";
import { useAction } from "@/useResource";

const props = defineProps({ staff: { type: Object, default: null } });
const emit = defineEmits(["close"]);

const roles = ["Warden", "Cook", "Cleaner", "Security Guard", "Manager", "Maintenance", "Other"];
const modes = ["UPI", "Bank Transfer", "Cash", "Cheque", "Other"];
const buildings = activeProperties();
const s = props.staff || {};
const form = reactive({
	staff_name: s.staff_name || "",
	role: s.role || "Warden",
	property: s.property || ui.property || buildings[0]?.name || "",
	mobile_no: s.mobile_no || "",
	monthly_salary: s.monthly_salary || "",
	pay_day: s.pay_day || 1,
	joining_date: s.joining_date || boot.today,
	leaving_date: s.leaving_date || "",
	payment_mode: s.payment_mode || "UPI",
	upi_id: s.upi_id || "",
	bank_account_no: s.bank_account_no || "",
	ifsc_code: s.ifsc_code || "",
	address: s.address || "",
	emergency_contact: s.emergency_contact || "",
	notes: s.notes || "",
});
const picture = ref(s.display_picture || "");

const { loading, run } = useAction(
	() =>
		post("save_staff", {
			data: {
				...form,
				name: s.name,
				leaving_date: form.leaving_date || null,
				...(picture.value !== (s.display_picture || "") && { picture: picture.value }),
			},
		}),
	{ success: () => `${form.staff_name} saved` }
);

async function save() {
	await run();
	emit("close");
}
</script>
