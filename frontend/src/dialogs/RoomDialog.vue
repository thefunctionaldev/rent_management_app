<template>
	<Modal
		open
		:title="room ? `Edit room ${room.room_number}` : 'Add room'"
		:subtitle="room ? room.property : 'Add a room or unit to a building'"
		@close="$emit('close')"
	>
		<form id="room-form" class="space-y-4" @submit.prevent="save">
			<Field v-if="!room && buildings.length > 1" label="Building" required>
				<select v-model="form.property" class="input" required>
					<option v-for="b in buildings" :key="b.name" :value="b.name">
						{{ b.name }}
					</option>
				</select>
			</Field>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Room number" required>
					<input
						v-model="form.room_number"
						class="input"
						required
						autofocus
						placeholder="101"
						:disabled="!!room"
					/>
				</Field>
				<Field label="Floor">
					<input
						v-model="form.floor"
						class="input"
						list="floor-options"
						placeholder="Ground"
					/>
					<datalist id="floor-options">
						<option v-for="f in floorOptions" :key="f" :value="f" />
					</datalist>
				</Field>
				<Field label="Beds" required hint="2 or more for shared rooms">
					<input
						v-model.number="form.capacity"
						class="input tabular"
						type="number"
						min="1"
						max="50"
						required
					/>
				</Field>
			</div>
			<Field v-if="room && !room.occupants.length" label="Status">
				<select v-model="form.status" class="input">
					<option>Available</option>
					<option>Reserved</option>
					<option>Under Renovation</option>
				</select>
			</Field>

			<div v-if="!newType">
				<div class="mb-1.5 flex items-center justify-between">
					<span class="label mb-0">Room type</span>
					<button
						type="button"
						class="text-xs font-medium text-brand-600 hover:underline"
						@click="newType = true"
					>
						+ New type
					</button>
				</div>
				<select v-model="form.room_type" class="input">
					<option value="">—</option>
					<option v-for="t in types.data.value || []" :key="t.name" :value="t.name">
						{{ t.name }} · {{ money(t.standard_rent) }}/mo
					</option>
				</select>
			</div>
			<div
				v-else
				class="space-y-4 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-4"
			>
				<div class="flex items-center justify-between">
					<p class="text-sm font-medium text-slate-900">New room type</p>
					<button
						type="button"
						class="text-xs text-slate-500 hover:underline"
						@click="newType = false"
					>
						Pick existing
					</button>
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<Field label="Type name" required>
						<input
							v-model="type.type"
							class="input"
							required
							placeholder="Single Room"
						/>
					</Field>
					<Field label="Standard rent" required>
						<input
							v-model="type.standard_rent"
							class="input tabular"
							type="number"
							min="0"
							required
						/>
					</Field>
					<Field label="Security deposit">
						<input
							v-model="type.security_deposit"
							class="input tabular"
							type="number"
							min="0"
						/>
					</Field>
					<div class="flex flex-col justify-end gap-2 pb-1 text-sm text-slate-700">
						<label class="flex items-center gap-2"
							><input
								v-model="type.is_furnished"
								type="checkbox"
								class="accent-brand-600"
							/>
							Furnished</label
						>
						<label class="flex items-center gap-2"
							><input
								v-model="type.has_attached_bathroom"
								type="checkbox"
								class="accent-brand-600"
							/>
							Attached bathroom</label
						>
					</div>
				</div>
			</div>

			<div class="rounded-xl border border-slate-200 px-4 py-1">
				<label class="flex items-center gap-2 py-2.5 text-sm text-slate-700">
					<input
						v-model="form.has_meter"
						type="checkbox"
						class="size-4 accent-brand-600"
					/>
					Has its own electricity meter
					<span class="text-slate-400">(billed to its tenants)</span>
				</label>
				<Field
					v-if="form.has_meter"
					label="Rate per unit"
					hint="Blank: the rate in Settings"
					class="pb-3"
				>
					<input
						v-model="form.electricity_rate"
						type="number"
						min="0"
						step="0.01"
						class="input tabular"
					/>
				</Field>
			</div>

			<Field
				:label="form.capacity > 1 ? 'Monthly rent per bed' : 'Monthly rent'"
				hint="Leave blank to use the room type's standard rent"
			>
				<input
					v-model="form.room_rent"
					class="input tabular"
					type="number"
					min="0"
					:placeholder="defaultRent"
				/>
			</Field>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="room-form" :loading="loading">{{
				room ? "Save" : "Add room"
			}}</Button>
		</template>
	</Modal>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { activeProperties, reloadProperties, ui } from "@/store";
import { useAction, useResource } from "@/useResource";
import { money } from "@/utils";

const props = defineProps({ room: { type: Object, default: null } });
const emit = defineEmits(["close"]);
const floorOptions = ["Ground", "First", "Second", "Third", "Fourth", "Fifth", "Terrace"];
const buildings = computed(() => activeProperties());

const form = reactive({
	room_number: props.room?.room_number || "",
	property: props.room?.property || ui.property || buildings.value[0]?.name || "",
	floor: props.room ? props.room.floor || "" : "Ground",
	capacity: props.room?.capacity || 1,
	status: props.room?.status || "Available",
	room_type: props.room?.room_type || "",
	room_rent: props.room?.room_rent || "",
	has_meter: !!props.room?.has_meter,
	electricity_rate: props.room?.electricity_rate || "",
});
const type = reactive({
	type: "",
	standard_rent: "",
	security_deposit: "",
	is_furnished: false,
	has_attached_bathroom: false,
});
const newType = ref(false);
const types = useResource(() => get("get_room_types"));

const defaultRent = computed(() => {
	if (newType.value) return type.standard_rent;
	const selected = types.data.value?.find((t) => t.name === form.room_type);
	return selected ? String(selected.standard_rent) : "";
});

const { loading, run } = useAction(
	async () => {
		let roomType = form.room_type;
		if (newType.value) {
			roomType = await post("create_room_type", {
				data: {
					...type,
					deposit_applicable: type.security_deposit > 0 ? 1 : 0,
					is_furnished: type.is_furnished ? 1 : 0,
					has_attached_bathroom: type.has_attached_bathroom ? 1 : 0,
				},
			});
		}
		return post("save_room", {
			data: {
				...form,
				name: props.room?.name,
				room_type: roomType || null,
				room_rent: form.room_rent || null,
				property: form.property || null,
				has_meter: form.has_meter ? 1 : 0,
				electricity_rate: form.electricity_rate || null,
				status: props.room ? form.status : "Available",
			},
		});
	},
	{ success: (name) => (props.room ? `Room ${name} saved` : `Room ${name} added`) }
);

async function save() {
	await run();
	reloadProperties();
	emit("close");
}
</script>
