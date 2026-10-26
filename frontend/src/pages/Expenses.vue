<template>
	<div>
		<PageHeader title="Expenses" subtitle="Salaries, bills and repairs for each building">
			<select v-model="period" class="input w-auto">
				<option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
			</select>
			<Button variant="primary" :icon="Plus" @click="openDialog('expense', { categories })"
				>Add expense</Button
			>
		</PageHeader>

		<div class="mb-6 grid gap-4 sm:grid-cols-3">
			<StatCard
				label="Total spent"
				:value="money(total)"
				:hint="periodLabel"
				:icon="Receipt"
				tone="rose"
			/>
			<div class="card p-5 sm:col-span-2">
				<p class="text-sm font-medium text-slate-500">By category</p>
				<div v-if="byCategory.length" class="mt-3 space-y-2">
					<div v-for="c in byCategory.slice(0, 5)" :key="c.category" class="text-sm">
						<div class="flex justify-between">
							<span class="text-slate-600">{{ c.category }}</span>
							<span class="tabular font-medium">{{ money(c.amount) }}</span>
						</div>
						<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
							<div
								class="h-full rounded-full bg-rose-400"
								:style="{ width: `${(c.amount / total) * 100}%` }"
							/>
						</div>
					</div>
				</div>
				<p v-else class="mt-3 text-sm text-slate-400">No expenses in this period</p>
			</div>
		</div>

		<div class="card">
			<div v-if="loading && !expenses.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 5" :key="i" class="h-10" />
			</div>
			<EmptyState
				v-else-if="!expenses.length"
				:icon="Receipt"
				title="No expenses yet"
				description="Record salaries, electricity bills and repairs to see your real profit."
			/>
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Date</th>
							<th class="table-head">Category</th>
							<th class="table-head">Paid to</th>
							<th v-if="!ui.property" class="table-head">Building</th>
							<th class="table-head text-right">Amount</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr
							v-for="x in expenses"
							:key="x.name"
							class="cursor-pointer transition hover:bg-slate-50/80"
							@click="openDialog('expense', { expense: x, categories })"
						>
							<td class="table-cell text-slate-600">{{ date(x.expense_date) }}</td>
							<td class="table-cell font-medium">{{ x.category }}</td>
							<td class="table-cell text-slate-600">
								{{ x.paid_to || "—" }}
								<p
									v-if="x.description"
									class="max-w-xs truncate text-xs text-slate-400"
								>
									{{ x.description }}
								</p>
							</td>
							<td v-if="!ui.property" class="table-cell text-slate-600">
								{{ x.property }}
							</td>
							<td class="table-cell tabular text-right font-semibold text-rose-600">
								{{ money(x.amount) }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Plus, Receipt } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { openDialog } from "@/dialogs";
import { boot, scope, ui } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

const iso = (d) =>
	new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const today = new Date(`${boot.today}T00:00:00`);
const monthRange = (offset) => {
	const start = new Date(today.getFullYear(), today.getMonth() - offset, 1);
	const end = new Date(today.getFullYear(), today.getMonth() - offset + 1, 0);
	return [
		iso(start),
		iso(end),
		start.toLocaleString("en-IN", { month: "long", year: "numeric" }),
	];
};
const periods = [
	{ value: "0", label: "This month", range: monthRange(0) },
	{ value: "1", label: "Last month", range: monthRange(1) },
	{
		value: "fy",
		label: "This financial year",
		range: (() => {
			const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
			return [
				`${year}-04-01`,
				`${year + 1}-03-31`,
				`FY ${year}-${String(year + 1).slice(2)}`,
			];
		})(),
	},
	{ value: "all", label: "All time", range: [null, null, "All time"] },
];
const period = ref("0");
const current = computed(() => periods.find((p) => p.value === period.value).range);
const periodLabel = computed(() => current.value[2]);

const { data, loading, reload } = useResource(() =>
	get("get_expenses", { from_date: current.value[0], to_date: current.value[1], ...scope() })
);
watch(period, reload);
const expenses = computed(() => data.value?.expenses || []);
const categories = computed(() => data.value?.categories || ["Other"]);
const total = computed(() => expenses.value.reduce((s, x) => s + x.amount, 0));
const byCategory = computed(() => {
	const sums = {};
	for (const x of expenses.value) sums[x.category] = (sums[x.category] || 0) + x.amount;
	return Object.entries(sums)
		.map(([category, amount]) => ({ category, amount }))
		.sort((a, b) => b.amount - a.amount);
});
</script>
