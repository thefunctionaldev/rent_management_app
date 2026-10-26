<template>
	<div>
		<PageHeader title="Profit & loss" subtitle="Rent collected minus expenses, month by month">
			<select v-model.number="months" class="input w-auto">
				<option :value="6">Last 6 months</option>
				<option :value="12">Last 12 months</option>
				<option :value="24">Last 24 months</option>
			</select>
		</PageHeader>

		<div v-if="locked" class="card flex flex-col items-center px-6 py-14 text-center">
			<span class="grid size-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">
				<TrendingUp class="size-6" />
			</span>
			<p class="mt-4 font-semibold">See what each building really earns</p>
			<p class="mt-1 max-w-md text-sm text-slate-500">
				The profit and loss report is part of the Growth and Pro plans. Your expenses are
				recorded either way.
			</p>
			<Button class="mt-5" variant="primary" href="/rent/billing">See plans</Button>
		</div>

		<template v-else-if="report">
			<div class="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Rent collected"
					:value="money(report.totals.collected)"
					:hint="`${money(report.totals.invoiced)} invoiced`"
					:icon="Wallet"
					tone="green"
				/>
				<StatCard
					label="Expenses"
					:value="money(report.totals.expenses)"
					:icon="Receipt"
					tone="rose"
				/>
				<StatCard
					label="Profit"
					:value="money(report.totals.profit)"
					:hint="
						report.totals.margin !== null
							? `${report.totals.margin}% of collections`
							: ''
					"
					:icon="TrendingUp"
					:tone="report.totals.profit >= 0 ? 'indigo' : 'rose'"
				/>
				<StatCard
					label="Average per month"
					:value="money(report.totals.profit / (activeMonths || 1))"
					:hint="`over ${activeMonths} month${
						activeMonths === 1 ? '' : 's'
					} with activity`"
					:icon="CalendarDays"
					tone="sky"
				/>
			</div>

			<div class="card mb-6 p-5">
				<BarChart :rows="chartRows" :series="series" />
			</div>

			<div class="grid gap-6 lg:grid-cols-3">
				<div class="card lg:col-span-2">
					<div class="overflow-x-auto">
						<table class="w-full">
							<thead class="border-b border-slate-100 bg-slate-50/60">
								<tr>
									<th class="table-head">Month</th>
									<th class="table-head text-right">Invoiced</th>
									<th class="table-head text-right">Collected</th>
									<th class="table-head text-right">Expenses</th>
									<th class="table-head text-right">Profit</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-slate-100">
								<tr v-for="m in [...report.months].reverse()" :key="m.month">
									<td class="table-cell font-medium">
										{{ monthLabel(m.month) }}
									</td>
									<td class="table-cell tabular text-right text-slate-500">
										{{ money(m.invoiced) }}
									</td>
									<td class="table-cell tabular text-right">
										{{ money(m.collected) }}
									</td>
									<td class="table-cell tabular text-right text-rose-600">
										{{ money(m.expenses) }}
									</td>
									<td
										class="table-cell tabular text-right font-semibold"
										:class="
											m.profit >= 0 ? 'text-emerald-600' : 'text-rose-600'
										"
									>
										{{ money(m.profit) }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
				<div class="space-y-6">
					<div v-if="!ui.property && report.properties.length > 1" class="card p-5">
						<h2 class="font-semibold">By building</h2>
						<ul class="mt-3 space-y-3 text-sm">
							<li
								v-for="p in report.properties"
								:key="p.property"
								class="flex justify-between gap-3"
							>
								<span class="truncate text-slate-600">{{ p.property }}</span>
								<span
									class="tabular font-medium"
									:class="p.profit >= 0 ? 'text-emerald-600' : 'text-rose-600'"
								>
									{{ money(p.profit) }}
								</span>
							</li>
						</ul>
					</div>
					<div class="card p-5">
						<h2 class="font-semibold">Where the money went</h2>
						<ul v-if="report.categories.length" class="mt-3 space-y-3 text-sm">
							<li
								v-for="c in report.categories"
								:key="c.category"
								class="flex justify-between gap-3"
							>
								<span class="text-slate-600">{{ c.category }}</span>
								<span class="tabular font-medium">{{ money(c.amount) }}</span>
							</li>
						</ul>
						<p v-else class="mt-3 text-sm text-slate-500">
							No expenses yet.
							<RouterLink
								to="/expenses"
								class="font-medium text-brand-600 hover:underline"
								>Add one</RouterLink
							>
						</p>
					</div>
				</div>
			</div>
		</template>
		<Skeleton v-else class="h-96" />
	</div>
</template>

<script setup>
import { CalendarDays, Receipt, TrendingUp, Wallet } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get } from "@/api";
import BarChart from "@/components/BarChart.vue";
import Button from "@/components/Button.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { boot, scope, ui } from "@/store";
import { useResource } from "@/useResource";
import { money } from "@/utils";

const months = ref(12);
const locked = computed(
	() => boot.subscription?.enforced && !boot.subscription?.features?.profit_report
);
const { data, reload } = useResource(() =>
	locked.value
		? Promise.resolve(null)
		: get("get_profit_and_loss", { months: months.value, ...scope() })
);
watch(months, reload);
const report = computed(() => data.value);
const activeMonths = computed(
	() => report.value.months.filter((m) => m.collected || m.expenses || m.invoiced).length
);

const series = [
	{ key: "collected", label: "Collected", color: "bg-emerald-500" },
	{ key: "expenses", label: "Expenses", color: "bg-rose-400" },
];
const monthLabel = (key) =>
	new Date(`${key}-01T00:00:00`).toLocaleString("en-IN", { month: "short", year: "numeric" });
const chartRows = computed(() =>
	report.value.months.map((m) => ({
		...m,
		label: m.month,
		short: new Date(`${m.month}-01T00:00:00`).toLocaleString("en-IN", { month: "short" }),
	}))
);
</script>
