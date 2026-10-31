<template>
	<div class="space-y-4">
		<div class="flex flex-wrap items-center gap-2">
			<select
				v-model="period"
				class="input w-auto py-1.5"
				aria-label="Period"
				@change="load"
			>
				<option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
			</select>
			<div class="flex-1" />
			<Button :icon="Download" :href="pdfUrl(range)">Statement (PDF)</Button>
		</div>

		<Skeleton v-if="!data" class="h-48" />
		<template v-else>
			<div class="grid grid-cols-3 gap-2 text-sm">
				<div class="rounded-xl bg-slate-50 p-3">
					<p class="text-xs text-slate-500">Billed</p>
					<p class="tabular font-semibold">{{ money(data.billed) }}</p>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<p class="text-xs text-slate-500">Paid</p>
					<p class="tabular font-semibold text-emerald-700">{{ money(data.paid) }}</p>
				</div>
				<div
					class="rounded-xl p-3"
					:class="data.balance > 0 ? 'bg-rose-50' : 'bg-slate-50'"
				>
					<p class="text-xs text-slate-500">
						{{
							data.balance > 0 ? "Due" : data.balance < 0 ? "In advance" : "Balance"
						}}
					</p>
					<p class="tabular font-semibold" :class="data.balance > 0 && 'text-rose-700'">
						{{ money(Math.abs(data.balance)) }}
					</p>
				</div>
			</div>

			<div class="overflow-hidden rounded-xl border border-slate-200">
				<p
					v-if="data.opening"
					class="flex justify-between bg-slate-50 px-4 py-2 text-xs text-slate-500"
				>
					<span>Opening balance</span
					><span class="tabular">{{ money(data.opening) }}</span>
				</p>
				<p v-if="!data.rows.length" class="px-4 py-6 text-center text-sm text-slate-500">
					Nothing in this period.
				</p>
				<ul class="divide-y divide-slate-100">
					<li v-for="r in data.rows" :key="r.ref" class="flex gap-3 px-4 py-2.5 text-sm">
						<span class="w-16 shrink-0 text-xs text-slate-500">{{
							shortDate(r.date)
						}}</span>
						<div class="min-w-0 flex-1">
							<p class="font-medium">{{ r.label }}</p>
							<p
								v-if="r.detail"
								class="truncate text-xs text-slate-400"
								:title="r.detail"
							>
								{{ r.detail }}
							</p>
						</div>
						<div class="text-right">
							<p
								class="tabular font-medium"
								:class="r.credit ? 'text-emerald-700' : ''"
							>
								{{ r.credit ? `−${money(r.credit)}` : money(r.debit) }}
							</p>
							<p class="tabular text-xs text-slate-400">{{ money(r.balance) }}</p>
						</div>
					</li>
				</ul>
			</div>

			<div
				v-for="d in data.deposits"
				:key="d.stay"
				class="rounded-xl border border-slate-200 p-4 text-sm"
			>
				<div class="flex justify-between">
					<p class="font-medium">Deposit · room {{ d.room }}</p>
					<p class="tabular">{{ money(d.amount) }}</p>
				</div>
				<p class="text-xs text-slate-500">
					{{
						d.collected
							? `Paid${d.collected_on ? ` on ${date(d.collected_on)}` : ""}`
							: "Not received"
					}}
					<template v-if="d.settlement">
						· settled {{ date(d.settlement.date) }}:
						<template v-if="d.settlement.owes"
							>{{ money(d.settlement.owes) }} still owed</template
						>
						<template v-else>{{ money(d.settlement.refund) }} refunded</template>
					</template>
				</p>
			</div>

			<!-- no dues -->
			<div
				class="rounded-xl p-4 text-sm"
				:class="data.no_dues.eligible ? 'bg-emerald-50' : 'bg-slate-50'"
			>
				<div class="flex flex-wrap items-center gap-3">
					<div class="min-w-0 flex-1">
						<p class="font-medium">No-dues certificate</p>
						<p v-if="data.no_dues.eligible" class="text-emerald-800">
							Nothing is owed, so a certificate can be downloaded.
						</p>
						<p v-else class="text-slate-500">
							Not yet: {{ data.no_dues.reasons.join(", ") }}.
						</p>
					</div>
					<Button
						v-if="data.no_dues.eligible"
						variant="primary"
						:icon="BadgeCheck"
						:href="noDuesUrl"
						>Download</Button
					>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { BadgeCheck, Download } from "lucide-vue-next";
import { computed, ref } from "vue";

import Button from "@/components/Button.vue";
import Skeleton from "@/components/Skeleton.vue";
import { boot } from "@/store";
import { date, money, shortDate } from "@/utils";

// fetch(args) returns the statement; pdfUrl(args) and noDuesUrl link to the PDFs
const props = defineProps({
	fetch: { type: Function, required: true },
	pdfUrl: { type: Function, required: true },
	noDuesUrl: { type: String, required: true },
	today: { type: String, default: "" },
});

// financial years run April to March
const today = props.today || boot.today;
const fyStart = (year) => `${year}-04-01`;
const thisFy = Number(today.slice(0, 4)) - (Number(today.slice(5, 7)) < 4 ? 1 : 0);
const periods = [
	{ value: "all", label: "Everything" },
	{ value: "fy", label: `This financial year (${thisFy}-${String(thisFy + 1).slice(2)})` },
	{ value: "last", label: `Last financial year (${thisFy - 1}-${String(thisFy).slice(2)})` },
	{ value: "90", label: "Last 3 months" },
];
const period = ref("all");
const range = computed(() => {
	if (period.value === "fy") return { from_date: fyStart(thisFy) };
	if (period.value === "last")
		return { from_date: fyStart(thisFy - 1), to_date: `${thisFy}-03-31` };
	if (period.value === "90") {
		const d = new Date(`${today}T00:00:00`);
		d.setDate(d.getDate() - 90);
		return {
			from_date: new Date(d.getTime() - d.getTimezoneOffset() * 60000)
				.toISOString()
				.slice(0, 10),
		};
	}
	return {};
});

const data = ref(null);
async function load() {
	data.value = null;
	data.value = await props.fetch(range.value);
}
load();
</script>
