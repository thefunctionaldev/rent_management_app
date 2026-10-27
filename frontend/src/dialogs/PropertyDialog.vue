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
			<details
				class="rounded-xl border border-slate-200 px-4 py-3"
				:open="!!form.description"
			>
				<summary class="cursor-pointer text-sm font-medium">Listing page</summary>
				<div class="mt-3 space-y-4">
					<label class="flex items-center gap-2 text-sm text-slate-700">
						<input
							v-model="form.show_on_listing"
							type="checkbox"
							class="size-4 accent-brand-600"
						/>
						Show this building on the listing page
					</label>
					<div class="grid gap-4 sm:grid-cols-2">
						<Field label="For">
							<select v-model="form.listing_for" class="input">
								<option value="">—</option>
								<option>Men</option>
								<option>Women</option>
								<option value="Anyone">Anyone (co-living)</option>
							</select>
						</Field>
						<Field label="Map link" hint="From Google Maps: Share > Copy link">
							<input v-model="form.map_link" class="input" type="url" />
						</Field>
					</div>
					<label class="flex items-center gap-2 text-sm text-slate-700">
						<input
							v-model="form.food_included"
							type="checkbox"
							class="size-4 accent-brand-600"
						/>
						Food included
					</label>
					<Field label="Description">
						<textarea
							v-model="form.description"
							class="input"
							rows="3"
							placeholder="Near the metro, 5 minutes from tech parks..."
						/>
					</Field>
					<Field label="Amenities" hint="One per line">
						<textarea
							v-model="form.amenities"
							class="input"
							rows="3"
							placeholder="WiFi&#10;Laundry&#10;Power backup"
						/>
					</Field>
				</div>
			</details>
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
	show_on_listing: p.show_on_listing ?? 1,
	listing_for: p.listing_for || "",
	food_included: !!p.food_included,
	map_link: p.map_link || "",
	description: p.description || "",
	amenities: p.amenities || "",
});
const picture = ref(p.image || "");

const { loading, run } = useAction(
	() =>
		post("save_property", {
			data: {
				...form,
				name: props.property?.name,
				is_active: form.is_active ? 1 : 0,
				show_on_listing: form.show_on_listing ? 1 : 0,
				food_included: form.food_included ? 1 : 0,
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
