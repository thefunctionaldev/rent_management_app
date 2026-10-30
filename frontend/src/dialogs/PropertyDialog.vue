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
					<div v-if="form.food_included" class="space-y-3 rounded-lg bg-slate-50 p-3">
						<div class="grid gap-3 sm:grid-cols-3">
							<label
								v-for="meal in ['breakfast', 'lunch', 'dinner']"
								:key="meal"
								class="space-y-1.5 text-sm"
							>
								<span class="flex items-center gap-2 capitalize">
									<input
										v-model="form[`serves_${meal}`]"
										type="checkbox"
										class="size-4 accent-brand-600"
									/>
									{{ meal }}
								</span>
								<input
									v-model="form[`${meal}_time`]"
									type="time"
									class="input"
									:disabled="!form[`serves_${meal}`]"
								/>
							</label>
						</div>
						<Field label="Tenants can skip a meal until" hint="hours before it">
							<input
								v-model.number="form.meal_skip_cutoff_hours"
								class="input tabular w-28"
								type="number"
								min="0"
							/>
						</Field>
					</div>
					<div class="grid gap-3 sm:grid-cols-2">
						<Field label="Gate closes at" hint="Curfew for night attendance">
							<input v-model="form.curfew_time" type="time" class="input" />
						</Field>
						<Field label="Visitors allowed until">
							<input v-model="form.visitors_until" type="time" class="input" />
						</Field>
					</div>
					<Field label="Description">
						<textarea
							v-model="form.description"
							class="input"
							rows="3"
							placeholder="Near the metro, 5 minutes from tech parks..."
						/>
					</Field>
					<div class="space-y-3 rounded-lg bg-slate-50 p-3">
						<p class="text-sm font-medium text-slate-700">
							Owner, if not you
							<span class="block text-xs font-normal text-slate-500"
								>Rent receipts for this building show who the rent is paid to</span
							>
						</p>
						<div class="grid gap-3 sm:grid-cols-2">
							<Field label="Owner name">
								<input v-model="form.owner_name" class="input" />
							</Field>
							<Field label="Owner PAN">
								<input
									v-model="form.owner_pan"
									class="input uppercase"
									maxlength="10"
								/>
							</Field>
						</div>
						<Field label="Owner address">
							<textarea v-model="form.owner_address" class="input" rows="2" />
						</Field>
					</div>
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
	serves_breakfast: p.serves_breakfast ?? 1,
	breakfast_time: (p.breakfast_time || "08:00").slice(0, 5),
	serves_lunch: p.serves_lunch ?? 1,
	lunch_time: (p.lunch_time || "13:00").slice(0, 5),
	serves_dinner: p.serves_dinner ?? 1,
	dinner_time: (p.dinner_time || "20:30").slice(0, 5),
	meal_skip_cutoff_hours: p.meal_skip_cutoff_hours ?? 4,
	curfew_time: (p.curfew_time || "22:30").slice(0, 5),
	visitors_until: (p.visitors_until || "21:00").slice(0, 5),
	owner_name: p.owner_name || "",
	owner_pan: p.owner_pan || "",
	owner_address: p.owner_address || "",
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
				serves_breakfast: form.serves_breakfast ? 1 : 0,
				serves_lunch: form.serves_lunch ? 1 : 0,
				serves_dinner: form.serves_dinner ? 1 : 0,
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
