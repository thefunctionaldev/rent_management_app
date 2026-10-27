<template>
	<div>
		<PageHeader title="Rooms" :subtitle="subtitle">
			<Button :icon="Plus" @click="openDialog('room')">Add room</Button>
			<Button variant="primary" :icon="KeyRound" @click="openDialog('allotRoom')"
				>Allot bed</Button
			>
		</PageHeader>

		<div class="mb-5 flex flex-wrap items-center gap-3">
			<div class="flex flex-wrap gap-1.5">
				<button
					v-for="s in statusFilters"
					:key="s.value"
					class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition"
					:class="
						status === s.value
							? 'bg-slate-900 text-white ring-slate-900'
							: 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
					"
					@click="status = s.value"
				>
					{{ s.label }}
					<span class="tabular text-xs opacity-60">{{ s.count }}</span>
				</button>
			</div>
			<select v-model="floor" class="input w-auto sm:ml-auto">
				<option value="">All floors</option>
				<option v-for="f in floors" :key="f" :value="f">{{ floorLabel(f) }}</option>
			</select>
		</div>

		<div v-if="loading && !rooms.length" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			<Skeleton v-for="i in 8" :key="i" class="h-52 rounded-2xl" />
		</div>

		<EmptyState
			v-else-if="!filtered.length"
			:icon="DoorOpen"
			title="No rooms here"
			:description="
				rooms.length ? 'Try a different filter.' : 'Add your first room to get started.'
			"
		>
			<div v-if="!rooms.length" class="flex flex-wrap justify-center gap-2">
				<Button variant="primary" :icon="Plus" @click="openDialog('room')"
					>Add room</Button
				>
				<Button href="/rent/import">Import from Excel</Button>
			</div>
		</EmptyState>

		<div v-for="group in groups" v-else :key="group.property" class="mb-8">
			<h2
				v-if="groups.length > 1"
				class="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700"
			>
				<img
					v-if="buildingImage(group.property)"
					:src="buildingImage(group.property)"
					alt=""
					class="size-7 rounded-md object-cover"
				/>
				<Building2 v-else class="size-4 text-slate-400" />{{ group.property }}
				<span class="font-normal text-slate-400">· {{ group.rooms.length }} rooms</span>
			</h2>
			<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
				<div
					v-for="room in group.rooms"
					:key="room.name"
					class="card group flex flex-col p-5 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-900/5"
				>
					<div class="flex items-start justify-between gap-2">
						<div class="min-w-0">
							<p class="truncate text-xs font-medium text-slate-500">
								{{ floorLabel(room.floor) }}
							</p>
							<p class="mt-0.5 text-2xl font-semibold tracking-tight">
								{{ room.room_number }}
							</p>
						</div>
						<div class="flex items-center gap-1">
							<StatusBadge :status="room.status" />
							<button
								class="rounded-md p-1 text-slate-400 opacity-0 transition group-hover:opacity-100 hover:bg-slate-100 hover:text-slate-700 focus:opacity-100"
								title="Edit room"
								@click="openDialog('room', { room })"
							>
								<Pencil class="size-3.5" />
							</button>
						</div>
					</div>
					<div class="mt-3 flex items-center gap-3 text-xs text-slate-500">
						<span v-if="room.room_type">{{ room.room_type }}</span>
						<span
							v-if="room.is_furnished"
							class="inline-flex items-center gap-1"
							title="Furnished"
							><Sofa class="size-3.5"
						/></span>
						<span
							v-if="room.has_attached_bathroom"
							class="inline-flex items-center gap-1"
							title="Attached bathroom"
							><Bath class="size-3.5"
						/></span>
					</div>
					<div class="mt-3 flex items-end justify-between gap-2">
						<p class="tabular text-sm">
							<span class="text-lg font-semibold">{{ money(room.room_rent) }}</span
							><span class="text-slate-500">
								/ {{ room.capacity > 1 ? "bed" : "month" }}</span
							>
						</p>
						<div
							v-if="room.capacity > 1"
							class="flex items-center gap-1"
							:title="`${room.occupants.length} of ${room.capacity} beds taken`"
						>
							<BedDouble
								v-for="bed in room.capacity"
								:key="bed"
								class="size-4"
								:class="isTaken(room, bed) ? 'text-brand-600' : 'text-slate-300'"
							/>
						</div>
					</div>

					<div
						class="mt-4 flex-1 space-y-2.5 border-t border-dashed border-slate-200 pt-4"
					>
						<div
							v-for="o in room.occupants"
							:key="o.name"
							class="flex items-center gap-2.5"
						>
							<RouterLink
								:to="`/tenants/${o.tenant}`"
								class="-m-1.5 flex min-w-0 flex-1 items-center gap-2.5 rounded-lg p-1.5 transition hover:bg-slate-50"
							>
								<Avatar
									:name="o.tenant_name"
									:image="o.tenant_picture"
									size="sm"
								/>
								<div class="min-w-0">
									<p class="truncate text-sm font-medium">{{ o.tenant_name }}</p>
									<p class="truncate text-xs whitespace-nowrap text-slate-500">
										{{ room.capacity > 1 ? `Bed ${o.bed_no} · ` : "" }}since
										{{ shortDate(o.allotment_date) }}
									</p>
								</div>
							</RouterLink>
							<span
								v-if="o.outstanding"
								class="tabular shrink-0 rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700"
								>{{ money(o.outstanding, { compact: true }) }}</span
							>
							<div class="flex shrink-0">
								<button
									class="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
									title="Create invoice"
									@click="openDialog('invoice', { allotment: o.name })"
								>
									<FilePlus class="size-4" />
								</button>
								<button
									class="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-rose-600"
									title="Vacate"
									@click="
										openDialog('vacate', {
											allotment: o.name,
											room: room.room_number,
											tenantName: o.tenant_name,
										})
									"
								>
									<LogOut class="size-4" />
								</button>
							</div>
						</div>
						<p v-if="!room.occupants.length" class="text-sm text-slate-400">
							No tenant
						</p>
					</div>

					<Button
						v-if="room.free_beds > 0 && room.status !== 'Under Renovation'"
						size="sm"
						:variant="room.occupants.length ? 'secondary' : 'primary'"
						class="mt-4 w-full"
						:icon="KeyRound"
						@click="openDialog('allotRoom', { room })"
					>
						{{
							room.capacity > 1 ? `Allot bed · ${room.free_beds} free` : "Allot room"
						}}
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Bath,
	BedDouble,
	Building2,
	DoorOpen,
	FilePlus,
	KeyRound,
	LogOut,
	Pencil,
	Plus,
	Sofa,
} from "lucide-vue-next";
import { computed, ref } from "vue";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { floorLabel, money, shortDate, sortFloors } from "@/utils";

const { data, loading } = useResource(() => get("get_rooms", scope()), { initial: [] });
const rooms = computed(() => data.value || []);
const status = ref("");
const floor = ref("");

const beds = computed(() => rooms.value.reduce((s, r) => s + r.capacity, 0));
const freeBeds = computed(() => rooms.value.reduce((s, r) => s + Math.max(r.free_beds, 0), 0));
const subtitle = computed(
	() =>
		`${rooms.value.length} rooms · ${beds.value} beds · ${freeBeds.value} free bed${
			freeBeds.value === 1 ? "" : "s"
		}`
);

const floors = computed(() => sortFloors([...new Set(rooms.value.map((r) => r.floor))]));
const statusFilters = computed(() => [
	{ value: "", label: "All", count: rooms.value.length },
	...["Available", "Partly Occupied", "Occupied", "Reserved", "Under Renovation"]
		.map((s) => ({
			value: s,
			label: s === "Partly Occupied" ? "Beds free" : s,
			count: rooms.value.filter((r) => r.status === s).length,
		}))
		.filter((s) => s.count || ["Available", "Occupied"].includes(s.value)),
]);
const filtered = computed(() =>
	rooms.value.filter(
		(r) =>
			(!status.value || r.status === status.value) &&
			(!floor.value || r.floor === floor.value)
	)
);
const buildingImage = (name) => boot.properties?.find((p) => p.name === name)?.image;
const groups = computed(() => {
	const byProperty = new Map();
	for (const room of filtered.value) {
		if (!byProperty.has(room.property)) byProperty.set(room.property, []);
		byProperty.get(room.property).push(room);
	}
	return [...byProperty].map(([property, list]) => ({ property, rooms: list }));
});

const isTaken = (room, bed) => room.occupants.some((o) => o.bed_no === bed);
</script>
