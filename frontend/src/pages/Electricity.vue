<template>
	<div>
		<PageHeader
			title="Electricity"
			subtitle="Meter readings are split between the room's tenants and added to their next rent invoice"
		>
			<input
				v-model="readingDate"
				type="date"
				class="input w-auto"
				aria-label="Reading date"
			/>
			<Button
				variant="primary"
				:icon="Save"
				:loading="saving"
				:disabled="!entered.length || entered.some((r) => preview(r).units < 0)"
				@click="save"
				>Save {{ entered.length || "" }} reading{{
					entered.length === 1 ? "" : "s"
				}}</Button
			>
		</PageHeader>

		<div
			v-if="data && !data.default_rate && rooms.some((r) => !r.rate)"
			class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
		>
			Set the electricity rate per unit in
			<RouterLink to="/settings" class="font-medium underline">Settings</RouterLink> so
			readings can be billed.
		</div>

		<div class="card mb-6">
			<div v-if="loading && !rooms.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 4" :key="i" class="h-10" />
			</div>
			<EmptyState
				v-else-if="!rooms.length"
				:icon="Zap"
				title="No rooms with a meter"
				description="Edit a room and tick 'Has electricity meter' to bill its electricity to the tenants."
			/>
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Room</th>
							<th class="table-head">Last reading</th>
							<th class="table-head w-40">New reading</th>
							<th class="table-head">New meter</th>
							<th class="table-head text-right">Units</th>
							<th class="table-head text-right">Amount</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr v-for="r in rooms" :key="r.name">
							<td class="table-cell">
								<p class="font-medium">{{ r.room_number }}</p>
								<p class="text-xs text-slate-500">
									{{ r.property }} · {{ r.occupied_beds }} tenant{{
										r.occupied_beds === 1 ? "" : "s"
									}}
								</p>
							</td>
							<td class="table-cell text-slate-600">
								<template v-if="r.last_reading !== null">
									<span class="tabular font-medium">{{ r.last_reading }}</span>
									<span class="text-xs text-slate-500">
										· {{ shortDate(r.last_reading_date) }}</span
									>
								</template>
								<span v-else class="text-xs text-slate-500"
									>First reading (opening)</span
								>
							</td>
							<td class="table-cell w-56 whitespace-normal">
								<input
									v-model="entries[r.name].reading"
									type="number"
									min="0"
									step="0.01"
									class="input tabular"
									:class="error(r) && 'border-rose-300'"
									:placeholder="r.last_reading ?? '0'"
								/>
								<p v-if="error(r)" class="mt-1 text-xs text-rose-600">
									{{ error(r) }}
								</p>
							</td>
							<td class="table-cell">
								<input
									v-model="entries[r.name].meter_replaced"
									type="checkbox"
									class="size-4 accent-brand-600"
									title="The meter was replaced and starts from zero"
								/>
							</td>
							<td class="table-cell tabular text-right">
								{{ preview(r).units ?? "—" }}
							</td>
							<td class="table-cell tabular text-right font-medium">
								{{
									preview(r).units !== null
										? money(preview(r).units * r.rate)
										: "—"
								}}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<div class="card">
			<div class="border-b border-slate-100 px-5 py-4">
				<h2 class="font-semibold">Recent readings</h2>
			</div>
			<EmptyState v-if="!history.length" :icon="Gauge" title="No readings yet" />
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Date</th>
							<th class="table-head">Room</th>
							<th class="table-head">Meter</th>
							<th class="table-head">Split</th>
							<th class="table-head text-right">Amount</th>
							<th class="table-head">Status</th>
							<th class="table-head" />
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr v-for="h in history" :key="h.name">
							<td class="table-cell text-slate-600">{{ date(h.reading_date) }}</td>
							<td class="table-cell font-medium">{{ h.room }}</td>
							<td class="table-cell tabular text-slate-600">
								<template v-if="h.status === 'Opening'"
									>{{ h.reading }}
									<span class="text-xs text-slate-500">(opening)</span></template
								>
								<template v-else
									>{{ h.previous_reading }} → {{ h.reading }}
									<span class="text-xs text-slate-500"
										>({{ h.units }} units)</span
									></template
								>
							</td>
							<td class="table-cell text-xs whitespace-normal text-slate-600">
								<span
									v-for="s in h.shares"
									:key="s.tenant_name"
									class="mr-3 inline-block"
								>
									{{ s.tenant_name }}: {{ money(s.amount) }}
									<span v-if="s.rent_invoice" class="text-emerald-600"
										>· {{ s.rent_invoice }}</span
									>
								</span>
							</td>
							<td class="table-cell tabular text-right">{{ money(h.amount) }}</td>
							<td class="table-cell"><StatusBadge :status="h.status" /></td>
							<td class="table-cell text-right">
								<button
									v-if="
										latest.has(h.name) &&
										['Opening', 'Unbilled', 'Not Billable'].includes(h.status)
									"
									class="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-rose-600"
									title="Delete reading"
									@click="remove(h)"
								>
									<Trash2 class="size-4" />
								</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Gauge, Save, Trash2, Zap } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { boot, bumpData, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const readingDate = ref(boot.today);
const { data, loading } = useResource(() => get("get_meter_rooms", scope()));
const rooms = computed(() => data.value?.rooms || []);
const readings = useResource(() => get("get_meter_readings", scope()), { initial: [] });
const history = computed(() => readings.data.value || []);
// only a room's latest reading can be deleted (history is newest first)
const latest = computed(() => {
	const seen = new Set();
	return new Set(
		history.value.filter((h) => !seen.has(h.room) && seen.add(h.room)).map((h) => h.name)
	);
});

const entries = reactive({});
const errors = reactive({});
watch(
	rooms,
	(list) => {
		for (const r of list) entries[r.name] ??= { reading: "", meter_replaced: false };
	},
	{ immediate: true }
);
const entered = computed(() =>
	rooms.value.filter((r) => entries[r.name] && entries[r.name].reading !== "")
);

function preview(r) {
	const e = entries[r.name];
	if (!e || e.reading === "" || r.last_reading === null) return { units: null };
	const units = e.meter_replaced ? Number(e.reading) : Number(e.reading) - r.last_reading;
	return { units: Math.round(units * 100) / 100 };
}
const error = (r) => errors[r.name] || (preview(r).units < 0 ? "Lower than last reading" : "");

const saving = ref(false);
async function save() {
	saving.value = true;
	try {
		const results = await post("save_meter_readings", {
			reading_date: readingDate.value,
			readings: entered.value.map((r) => ({
				room: r.name,
				reading: entries[r.name].reading,
				meter_replaced: entries[r.name].meter_replaced ? 1 : 0,
			})),
		});
		let saved = 0;
		for (const result of results) {
			errors[result.room] = result.error || "";
			if (!result.error) {
				entries[result.room].reading = "";
				entries[result.room].meter_replaced = false;
				saved++;
			}
		}
		if (saved) toast(`${saved} reading${saved === 1 ? "" : "s"} saved`);
		if (results.some((r) => r.error)) toast("Some readings need fixing", "error");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}

async function remove(h) {
	try {
		await post("delete_meter_reading", { name: h.name });
		toast("Reading deleted");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
