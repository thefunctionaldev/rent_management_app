<template>
	<div>
		<PageHeader title="Activity" subtitle="Who did what, and when" />

		<div class="mb-4 flex flex-wrap items-center gap-2">
			<select v-model="filters.user" class="input w-48">
				<option value="">Everyone</option>
				<option v-for="[user, name] in data?.people || []" :key="user" :value="user">
					{{ name || user }}
				</option>
			</select>
			<input v-model="filters.from" type="date" class="input w-40" :max="filters.to" />
			<span class="text-sm text-slate-400">to</span>
			<input v-model="filters.to" type="date" class="input w-40" :max="boot.today" />
		</div>
		<div class="mb-5 flex flex-wrap gap-1.5">
			<button
				v-for="c in ['', ...(data?.categories || [])]"
				:key="c"
				class="rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition"
				:class="
					filters.category === c
						? 'bg-slate-900 text-white ring-slate-900'
						: 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
				"
				@click="filters.category = c"
			>
				{{ c || "All" }}
			</button>
		</div>

		<div v-if="!data" class="space-y-3">
			<Skeleton v-for="i in 4" :key="i" class="h-16" />
		</div>
		<EmptyState
			v-else-if="!data.rows.length"
			:icon="History"
			title="Nothing in these days"
			description="Payments, rent changes, expenses, salaries, leave, settings and more show up here as they happen."
		/>
		<div v-for="day in days" :key="day.date" class="mb-6">
			<h3 class="mb-2 text-sm font-semibold text-slate-700">{{ dayLabel(day.date) }}</h3>
			<ul class="card divide-y divide-slate-100">
				<li
					v-for="row in day.rows"
					:key="row.name"
					class="flex items-start gap-3 px-5 py-3"
				>
					<Avatar :name="row.user_name || row.user" size="sm" />
					<div class="min-w-0 flex-1 text-sm">
						<p>
							<b class="font-semibold">{{ row.user_name || row.user }}</b>
							{{ row.summary }}
						</p>
						<p class="mt-0.5 text-xs text-slate-500">
							{{ time(row.creation) }} · {{ row.category }}
							<template v-if="row.property"> · {{ row.property }}</template>
							<RouterLink
								v-if="row.tenant"
								:to="`/tenants/${row.tenant}`"
								class="text-brand-600 hover:underline"
							>
								· tenant</RouterLink
							>
						</p>
					</div>
					<span
						class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium"
						:class="tones[row.category] || 'bg-slate-100 text-slate-600'"
						>{{ row.category }}</span
					>
				</li>
			</ul>
		</div>
		<p v-if="data?.more" class="text-center text-xs text-slate-500">
			Showing the latest 300. Narrow the dates or pick a person to see more.
		</p>
	</div>
</template>

<script setup>
import { History } from "lucide-vue-next";
import { computed, reactive, watch } from "vue";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { date } from "@/utils";

const weekAgo = (() => {
	const d = new Date(`${boot.today}T00:00:00`);
	d.setDate(d.getDate() - 6);
	return d.toLocaleDateString("en-CA");
})();
const filters = reactive({ user: "", category: "", from: weekAgo, to: boot.today });
const { data, reload } = useResource(() =>
	get("get_activity", {
		user: filters.user,
		category: filters.category,
		from_date: filters.from,
		to_date: filters.to,
		...scope(),
	})
);
watch(filters, reload);

const tones = {
	Payments: "bg-emerald-50 text-emerald-700",
	Invoices: "bg-brand-50 text-brand-700",
	Stays: "bg-sky-50 text-sky-700",
	Deposits: "bg-violet-50 text-violet-700",
	Expenses: "bg-amber-50 text-amber-800",
	Cash: "bg-emerald-50 text-emerald-800",
	Staff: "bg-slate-100 text-slate-700",
	Settings: "bg-slate-100 text-slate-700",
	Privacy: "bg-rose-50 text-rose-700",
};
const days = computed(() => {
	const byDay = new Map();
	for (const row of data.value?.rows || []) {
		const day = row.creation.slice(0, 10);
		if (!byDay.has(day)) byDay.set(day, { date: day, rows: [] });
		byDay.get(day).rows.push(row);
	}
	return [...byDay.values()];
});
function dayLabel(day) {
	if (day === boot.today) return "Today";
	const y = new Date(`${boot.today}T00:00:00`);
	y.setDate(y.getDate() - 1);
	return day === y.toLocaleDateString("en-CA") ? "Yesterday" : date(day);
}
const time = (value) =>
	new Date(value.replace(" ", "T")).toLocaleTimeString("en-IN", {
		hour: "numeric",
		minute: "2-digit",
	});
</script>
