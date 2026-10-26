<template>
	<Modal open title="Allot room" :subtitle="subtitle" width="lg" @close="$emit('close')">
		<form id="allot-form" class="space-y-5" @submit.prevent="save">
			<div class="grid gap-4" :class="bedChoices.length > 1 && 'sm:grid-cols-[1fr_9rem]'">
				<Field v-if="!room" label="Room" required>
					<select v-model="form.room" class="input" required>
						<option value="" disabled>Select a room with a free bed</option>
						<option v-for="r in availableRooms" :key="r.name" :value="r.name">
							{{ roomLabel(r) }}
						</option>
					</select>
				</Field>
				<Field v-if="bedChoices.length > 1" label="Bed">
					<select v-model.number="form.bed_no" class="input">
						<option v-for="b in bedChoices" :key="b" :value="b">Bed {{ b }}</option>
					</select>
				</Field>
			</div>

			<div>
				<div class="mb-1.5 flex items-center justify-between">
					<span class="label mb-0">Tenant<span class="text-rose-500"> *</span></span>
					<button
						type="button"
						class="text-xs font-medium text-brand-600 hover:underline"
						@click="newTenant = !newTenant"
					>
						{{ newTenant ? "Pick existing tenant" : "+ New tenant" }}
					</button>
				</div>
				<div
					v-if="newTenant"
					class="grid gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-4 sm:grid-cols-3"
				>
					<input
						v-model="tenant.first_name"
						class="input"
						placeholder="First name"
						required
					/>
					<input v-model="tenant.last_name" class="input" placeholder="Last name" />
					<input
						v-model="tenant.mobile_no"
						class="input"
						placeholder="Mobile"
						type="tel"
					/>
				</div>
				<template v-else>
					<SearchInput v-model="search" placeholder="Search tenants by name or phone" />
					<div
						class="mt-2 max-h-52 divide-y divide-slate-100 overflow-y-auto rounded-xl border border-slate-200"
					>
						<button
							v-for="t in filteredTenants"
							:key="t.name"
							type="button"
							class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-slate-50"
							:class="String(form.tenant) === String(t.name) && 'bg-brand-50/70'"
							@click="form.tenant = t.name"
						>
							<Avatar :name="t.full_name" size="sm" />
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-medium text-slate-900">
									{{ t.full_name }}
								</p>
								<p class="truncate text-xs text-slate-500">
									{{ t.mobile_no || "No phone" }}
								</p>
							</div>
							<span v-if="t.room" class="text-xs text-slate-400"
								>In {{ t.room }}</span
							>
							<CircleCheck
								v-if="String(form.tenant) === String(t.name)"
								class="size-4 text-brand-600"
							/>
						</button>
						<p
							v-if="!filteredTenants.length"
							class="px-3 py-6 text-center text-sm text-slate-500"
						>
							No tenants found
						</p>
					</div>
				</template>
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Move-in date" required>
					<input v-model="form.allotment_date" type="date" class="input" required />
				</Field>
				<Field label="Monthly rent" required>
					<input
						v-model="form.rent_amount"
						type="number"
						min="0"
						class="input tabular"
						required
					/>
				</Field>
				<Field label="Security deposit">
					<input
						v-model="form.security_deposit"
						type="number"
						min="0"
						class="input tabular"
					/>
				</Field>
			</div>
			<label
				v-if="form.security_deposit > 0"
				class="flex items-center gap-2 text-sm text-slate-700"
			>
				<input
					v-model="form.deposit_collected"
					type="checkbox"
					class="size-4 accent-brand-600"
				/>
				Deposit of {{ money(form.security_deposit) }} has been collected
			</label>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button
				variant="primary"
				type="submit"
				form="allot-form"
				:loading="loading"
				:icon="KeyRound"
			>
				Allot room
			</Button>
		</template>
	</Modal>
</template>

<script setup>
import { CircleCheck, KeyRound } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import SearchInput from "@/components/SearchInput.vue";
import { boot, scope, toast } from "@/store";
import { useAction, useResource } from "@/useResource";
import { floorLabel, money } from "@/utils";

const props = defineProps({
	room: { type: Object, default: null },
	tenantName: { type: [String, Number], default: null },
});
const emit = defineEmits(["close"]);

const form = reactive({
	room: props.room?.name || "",
	tenant: props.tenantName || "",
	allotment_date: boot.today,
	rent_amount: props.room?.room_rent || "",
	security_deposit: "",
	deposit_collected: false,
	bed_no: null,
});
const tenant = reactive({ first_name: "", last_name: "", mobile_no: "" });
const newTenant = ref(false);
const search = ref("");

const rooms = useResource(() => get("get_rooms", scope()), { initial: [] });
const types = useResource(() => get("get_room_types"), { initial: [] });
const tenants = useResource(() => get("get_tenants", { status: "Active" }), { initial: [] });

const availableRooms = computed(() =>
	rooms.data.value.filter((r) => r.free_beds > 0 && r.status !== "Under Renovation")
);
const selectedRoom = computed(
	() => props.room || rooms.data.value.find((r) => r.name === form.room)
);
const multipleBuildings = computed(
	() => new Set(rooms.data.value.map((r) => r.property)).size > 1
);
function roomLabel(r) {
	const parts = [r.room_number];
	if (multipleBuildings.value) parts.push(r.property);
	if (r.floor) parts.push(floorLabel(r.floor));
	if (r.capacity > 1) parts.push(`${r.free_beds} of ${r.capacity} beds free`);
	else if (r.room_type) parts.push(r.room_type);
	return parts.join(" · ");
}
const bedChoices = computed(() => {
	const room = selectedRoom.value;
	if (!room) return [];
	const taken = new Set((room.occupants || []).map((o) => o.bed_no));
	return Array.from({ length: room.capacity || 1 }, (_, i) => i + 1).filter(
		(b) => !taken.has(b)
	);
});
watch(bedChoices, (beds) => (form.bed_no = beds[0] || null), { immediate: true });
const subtitle = computed(() => {
	const room = selectedRoom.value;
	if (!room) return "Move a tenant in";
	return [`Room ${room.room_number}`, room.property, room.floor && floorLabel(room.floor)]
		.filter(Boolean)
		.join(" · ");
});
const filteredTenants = computed(() => {
	const q = search.value.toLowerCase();
	return tenants.data.value.filter(
		(t) => !q || t.full_name.toLowerCase().includes(q) || (t.mobile_no || "").includes(q)
	);
});

// prefill rent and deposit from the room and its type
watch(
	[selectedRoom, () => types.data.value],
	([room, roomTypes]) => {
		if (!room) return;
		form.rent_amount = room.room_rent || form.rent_amount;
		const roomType = roomTypes.find((t) => t.name === room.room_type);
		if (roomType?.deposit_applicable) form.security_deposit = roomType.security_deposit;
	},
	{ immediate: true }
);

const { loading, run } = useAction(
	async () => {
		let tenantName = form.tenant;
		if (newTenant.value) {
			tenantName = await post("save_tenant", { data: { ...tenant } });
		}
		return post("allot_room", {
			...form,
			tenant: tenantName,
			deposit_collected: form.deposit_collected ? 1 : 0,
		});
	},
	{ success: () => `Room ${selectedRoom.value?.room_number} allotted` }
);

async function save() {
	if (!newTenant.value && !form.tenant) {
		toast("Select a tenant", "error");
		return;
	}
	await run();
	emit("close");
}
</script>
