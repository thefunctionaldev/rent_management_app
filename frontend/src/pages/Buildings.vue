<template>
	<div>
		<PageHeader
			title="Buildings"
			:subtitle="`${properties.length} building${properties.length === 1 ? '' : 's'}`"
		>
			<Button variant="primary" :icon="Plus" @click="openDialog('property')"
				>Add building</Button
			>
		</PageHeader>

		<div v-if="loading && !properties.length" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
			<Skeleton v-for="i in 3" :key="i" class="h-44 rounded-2xl" />
		</div>
		<div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
			<div
				v-for="p in properties"
				:key="p.name"
				class="card flex flex-col p-5"
				:class="!p.is_active && 'opacity-60'"
			>
				<div class="flex items-start justify-between gap-3">
					<div class="flex min-w-0 items-center gap-3">
						<span
							class="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600"
						>
							<Building2 class="size-5" />
						</span>
						<div class="min-w-0">
							<p class="truncate font-semibold">{{ p.name }}</p>
							<p class="truncate text-xs text-slate-500">
								{{ [p.city, p.state].filter(Boolean).join(", ") || p.abbr }}
							</p>
						</div>
					</div>
					<StatusBadge v-if="!p.is_active" status="Inactive" />
					<button
						v-else
						class="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
						title="Edit building"
						@click="openDialog('property', { property: p })"
					>
						<Pencil class="size-4" />
					</button>
				</div>
				<div class="mt-5 grid grid-cols-3 gap-3 text-center">
					<div class="rounded-xl bg-slate-50 py-3">
						<p class="tabular text-lg font-semibold">{{ p.rooms }}</p>
						<p class="text-xs text-slate-500">Rooms</p>
					</div>
					<div class="rounded-xl bg-slate-50 py-3">
						<p class="tabular text-lg font-semibold">{{ p.beds }}</p>
						<p class="text-xs text-slate-500">Beds</p>
					</div>
					<div class="rounded-xl bg-slate-50 py-3">
						<p class="tabular text-lg font-semibold">{{ occupancy(p) }}%</p>
						<p class="text-xs text-slate-500">Occupied</p>
					</div>
				</div>
				<div class="mt-4 flex gap-2">
					<Button size="sm" class="flex-1" :icon="DoorOpen" @click="openRooms(p)"
						>View rooms</Button
					>
					<Button
						v-if="!p.is_active"
						size="sm"
						variant="ghost"
						@click="openDialog('property', { property: p })"
						>Edit</Button
					>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Building2, DoorOpen, Pencil, Plus } from "lucide-vue-next";
import { computed } from "vue";
import { useRouter } from "vue-router";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { boot, setProperty } from "@/store";
import { useResource } from "@/useResource";

const router = useRouter();
// unscoped: this page lists every building
const { data, loading } = useResource(
	async () => {
		boot.properties = await get("get_properties");
		return boot.properties;
	},
	{ initial: [] }
);
const properties = computed(() => data.value || []);

const occupancy = (p) => (p.beds ? Math.round((p.occupied_beds / p.beds) * 100) : 0);

function openRooms(p) {
	setProperty(p.name);
	router.push("/rooms");
}
</script>
