<template>
	<div>
		<PageHeader
			title="Occupancy calendar"
			subtitle="See each bed, current stays and upcoming departures."
			><Button @click="shift(-14)">← Previous</Button
			><Button @click="start = boot.today">Today</Button
			><Button @click="shift(14)">Next →</Button></PageHeader
		>
		<div class="mb-5 flex flex-wrap items-end gap-4">
			<Field label="From"
				><input v-model="start" class="input" type="date" required
			/></Field>
			<Field label="View"
				><select v-model.number="length" class="input">
					<option :value="14">14 days</option>
					<option :value="31">31 days</option>
				</select></Field
			>
			<Field label="Find a room"
				><input v-model="search" class="input" placeholder="Room or building"
			/></Field>
		</div>
		<p class="mb-4 text-sm text-slate-500">
			A notice date is an expected departure, not guaranteed availability. Bookings below
			hold capacity without a bed assignment. This view does not create or move bookings.
		</p>
		<p v-if="error" role="alert" class="mb-4 text-rose-700">{{ error }}</p>
		<p v-if="loading" role="status" class="mb-3 text-sm">Loading occupancy…</p>
		<div
			v-if="!error"
			class="card overflow-x-auto"
			tabindex="0"
			aria-label="Occupancy timeline, scroll horizontally"
		>
			<table class="w-full border-collapse text-xs">
				<caption class="sr-only">
					Bed occupancy from
					{{
						start
					}}
					to
					{{
						end
					}}. Status is written in each cell.
				</caption>
				<thead>
					<tr>
						<th class="sticky left-0 z-10 min-w-44 bg-white p-4 text-left">
							Room / bed
						</th>
						<th
							v-for="day in days"
							:key="day"
							class="min-w-24 p-3"
							:class="
								day === boot.today ? 'bg-brand-50 text-brand-700' : 'bg-slate-50'
							"
						>
							{{ day.slice(5) }}
						</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="bed in beds" :key="bed.key" class="border-t border-slate-100">
						<th scope="row" class="sticky left-0 z-10 bg-white p-3 text-left">
							<span class="block font-semibold"
								>{{ bed.room.room_number }} · Bed {{ bed.number }}</span
							><span class="font-normal text-slate-500">{{
								bed.room.property
							}}</span>
						</th>
						<td v-for="day in days" :key="day" class="p-1">
							<div class="min-h-16 rounded-lg p-2" :class="cell(bed, day).tone">
								<RouterLink
									v-if="cell(bed, day).tenant"
									:to="`/tenants/${cell(bed, day).tenant}`"
									class="font-medium underline"
									>{{ cell(bed, day).label }}</RouterLink
								><span v-else>{{ cell(bed, day).label }}</span
								><span v-if="cell(bed, day).notice" class="mt-1 block font-medium"
									>Expected move-out</span
								>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
			<p v-if="!loading && !beds.length" class="p-8 text-center text-slate-500">
				No rooms match. Add rooms in Setup or choose another building.
			</p>
		</div>
		<section class="card mt-6 p-6">
			<h2 class="text-lg font-semibold">Booked arrivals · capacity held</h2>
			<p class="mt-1 text-sm text-slate-500">
				All open bookings for the selected building, including arrivals outside this date
				range. Beds are assigned at move-in.
			</p>
			<ul class="mt-4 divide-y divide-slate-100">
				<li
					v-for="b in data?.bookings || []"
					:key="b.name"
					class="flex flex-wrap justify-between gap-2 py-3 text-sm"
				>
					<span
						>{{ b.lead_name }} · {{ b.property }} ·
						{{ b.room || b.room_type || "Room not assigned" }}</span
					><RouterLink to="/leads" class="text-brand-600"
						>{{ b.move_in_date || "Arrival date pending" }} →</RouterLink
					>
				</li>
			</ul>
			<p v-if="data && !data.bookings.length" class="mt-4 text-sm text-slate-500">
				No open bookings.
			</p>
		</section>
	</div>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { get } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import PageHeader from "@/components/PageHeader.vue";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { occupancyCell, addDate } from "@/occupancy";
const start = ref(boot.today),
	length = ref(14),
	search = ref("");
const end = computed(() => addDate(start.value, length.value - 1));
const days = computed(() =>
	start.value ? Array.from({ length: length.value }, (_, i) => addDate(start.value, i)) : [],
);
const { data, loading, error, reload } = useResource(() =>
	get("get_occupancy_calendar", { start_date: start.value, end_date: end.value, ...scope() }),
);
watch([start, length], () => {
	if (start.value) reload();
});
const beds = computed(() =>
	(data.value?.rooms || [])
		.filter((r) =>
			`${r.room_number} ${r.property}`.toLowerCase().includes(search.value.toLowerCase()),
		)
		.flatMap((room) =>
			Array.from({ length: Math.max(1, room.capacity || 1) }, (_, i) => ({
				key: `${room.name}:${i + 1}`,
				room,
				number: i + 1,
			})),
		),
);
const stays = computed(() => {
	const groups = {};
	for (const s of data.value?.stays || []) (groups[`${s.room}:${s.bed_no}`] ||= []).push(s);
	return groups;
});
const cell = (bed, day) => occupancyCell(bed, day, stays.value[bed.key] || []);
function shift(n) {
	start.value = addDate(start.value, n);
}
</script>
