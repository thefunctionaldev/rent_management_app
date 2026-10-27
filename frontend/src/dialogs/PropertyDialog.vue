<template>
	<Modal
		open
		:title="property ? `Edit ${property.name}` : 'Add building'"
		subtitle="A PG, hostel or apartment block with its own rooms"
		@close="$emit('close')"
	>
		<form id="property-form" class="space-y-4" @submit.prevent="save">
			<PictureInput v-model="picture" :name="form.property_name" />
			<div class="grid gap-4 sm:grid-cols-[1fr_8rem]">
				<Field label="Building name" required>
					<input
						v-model="form.property_name"
						class="input"
						required
						autofocus
						placeholder="Sunrise PG"
						:disabled="!!property"
					/>
				</Field>
				<Field label="Short code" hint="e.g. SPG">
					<input v-model="form.abbr" class="input uppercase" maxlength="10" />
				</Field>
			</div>
			<Field label="Address">
				<textarea v-model="form.address" class="input" rows="2" />
			</Field>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="City"><input v-model="form.city" class="input" /></Field>
				<Field label="State"><input v-model="form.state" class="input" /></Field>
				<Field label="Pincode"><input v-model="form.pincode" class="input" /></Field>
			</div>
			<label v-if="property" class="flex items-center gap-2 text-sm text-slate-700">
				<input v-model="form.is_active" type="checkbox" class="size-4 accent-brand-600" />
				Active (inactive buildings are hidden and don't count towards your plan)
			</label>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="property-form" :loading="loading">{{
				property ? "Save" : "Add building"
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
import { reloadProperties } from "@/store";
import { useAction } from "@/useResource";

const props = defineProps({ property: { type: Object, default: null } });
const emit = defineEmits(["close"]);

const p = props.property || {};
const form = reactive({
	property_name: p.property_name || "",
	abbr: p.abbr || "",
	address: p.address || "",
	city: p.city || "",
	state: p.state || "",
	pincode: p.pincode || "",
	is_active: p.is_active ?? 1,
});
const picture = ref(p.image || "");

const { loading, run } = useAction(
	() =>
		post("save_property", {
			data: {
				...form,
				name: props.property?.name,
				is_active: form.is_active ? 1 : 0,
				...(picture.value !== (p.image || "") && { picture: picture.value }),
			},
		}),
	{ success: (name) => `${name} saved` }
);

async function save() {
	await run();
	await reloadProperties();
	emit("close");
}
</script>
