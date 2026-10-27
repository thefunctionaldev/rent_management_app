<template>
	<Modal
		open
		:title="`Move in ${lead.lead_name}`"
		subtitle="Makes their tenant profile and gives them the bed"
		@close="$emit('close')"
	>
		<form id="move-in-form" class="space-y-4" @submit.prevent="save">
			<Field label="Room" required>
				<select v-model="form.room" class="input" required>
					<option value="" disabled>Choose a room with a free bed</option>
					<option v-for="r in freeRooms" :key="r.name" :value="r.name">
						{{ r.room_number }} · {{ r.room_type }} · {{ r.free_beds }} free ·
						{{ money(r.room_rent) }}
					</option>
				</select>
			</Field>
			<p v-if="rooms.data.value && !freeRooms.length" class="text-sm text-amber-700">
				No free beds in {{ lead.property }} right now.
			</p>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Moving in" required>
					<input v-model="form.allotment_date" class="input" type="date" required />
				</Field>
				<Field label="Monthly rent" required>
					<input
						v-model="form.rent_amount"
						class="input tabular"
						type="number"
						min="1"
						required
					/>
				</Field>
				<Field label="Deposit">
					<input
						v-model="form.security_deposit"
						class="input tabular"
						type="number"
						min="0"
					/>
				</Field>
			</div>
			<label class="flex items-center gap-2 text-sm">
				<input
					v-model="form.deposit_collected"
					type="checkbox"
					class="size-4 accent-brand-600"
				/>
				Deposit received
			</label>
			<p
				v-if="lead.token_status === 'Paid'"
				class="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
			>
				The {{ money(lead.token_amount) }} token is recorded as rent paid: on their first
				invoice, and the next one if the first month is shorter.
			</p>
			<p
				v-else-if="lead.token_status === 'Reported'"
				class="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
			>
				Their UPI token isn't confirmed yet. Confirm it first if you received it, so it
				counts towards the rent.
			</p>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="move-in-form" :loading="loading"
				>Move in</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import { useRouter } from "vue-router";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot } from "@/store";
import { useAction, useResource } from "@/useResource";
import { money } from "@/utils";

const props = defineProps({ lead: { type: Object, required: true } });
const emit = defineEmits(["close"]);
const router = useRouter();

const rooms = useResource(() => get("get_rooms", { property: props.lead.property }));
const types = useResource(() => get("get_room_types"), { initial: [] });
// the room they asked for first, then the held one
const freeRooms = computed(() =>
	(rooms.data.value || [])
		.filter((r) => r.free_beds > 0 && r.status !== "Under Renovation")
		.sort(
			(a, b) =>
				(b.room_type === props.lead.room_type) - (a.room_type === props.lead.room_type)
		)
);

const form = reactive({
	room: props.lead.room || "",
	allotment_date: props.lead.move_in_date || boot.today,
	rent_amount: "",
	security_deposit: "",
	deposit_collected: false,
});
watch(
	() => [form.room, rooms.data.value, types.data.value],
	() => {
		const room = (rooms.data.value || []).find((r) => r.name === form.room);
		if (!room) return;
		form.rent_amount = room.room_rent;
		const type = types.data.value.find((t) => t.name === room.room_type);
		form.security_deposit = type?.deposit_applicable ? type.security_deposit : 0;
	}
);

const { loading, run } = useAction(
	() =>
		post("move_in_lead", {
			name: props.lead.name,
			...form,
			deposit_collected: form.deposit_collected ? 1 : 0,
		}),
	{ success: `${props.lead.lead_name} moved in` }
);

async function save() {
	const result = await run();
	emit("close");
	router.push(`/tenants/${result.tenant}`);
}
</script>
