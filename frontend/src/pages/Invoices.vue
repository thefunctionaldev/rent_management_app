<template>
	<div>
		<PageHeader title="Invoices" subtitle="Monthly rent invoices for every tenant">
			<Button :icon="Sparkles" @click="openDialog('generateInvoices')"
				>Generate for month</Button
			>
			<Button variant="primary" :icon="Plus" @click="openDialog('invoice')"
				>New invoice</Button
			>
		</PageHeader>

		<div class="card">
			<div class="px-5 pt-4">
				<Tabs v-model="status" :tabs="tabs" />
			</div>
			<div class="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
				<SearchInput
					v-model="search"
					class="sm:w-72"
					placeholder="Search tenant, room or invoice"
				/>
				<select v-model="month" class="input sm:w-40">
					<option value="">All months</option>
					<option v-for="m in boot.months" :key="m">{{ m }}</option>
				</select>
				<input
					v-model="year"
					type="number"
					class="input tabular sm:w-28"
					placeholder="Year"
				/>
			</div>

			<div v-if="loading && !invoices.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 6" :key="i" class="h-10" />
			</div>
			<EmptyState
				v-else-if="!invoices.length"
				:icon="FileText"
				title="No invoices"
				description="Generate this month's invoices or create one manually."
			>
				<Button variant="primary" :icon="Sparkles" @click="openDialog('generateInvoices')"
					>Generate invoices</Button
				>
			</EmptyState>
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Invoice</th>
							<th class="table-head">Tenant</th>
							<th class="table-head">Period</th>
							<th class="table-head">Due</th>
							<th class="table-head text-right">Amount</th>
							<th class="table-head text-right">Balance</th>
							<th class="table-head">Status</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr
							v-for="inv in invoices"
							:key="inv.name"
							class="cursor-pointer transition hover:bg-slate-50/80"
							@click="selected = inv.name"
						>
							<td class="table-cell font-medium text-slate-900">{{ inv.name }}</td>
							<td class="table-cell">
								<p class="font-medium">{{ inv.tenant_name }}</p>
								<p class="text-xs text-slate-500">Room {{ inv.room }}</p>
							</td>
							<td class="table-cell text-slate-600">
								{{ inv.billing_month }} {{ inv.billing_year }}
							</td>
							<td
								class="table-cell"
								:class="
									inv.status === 'Overdue' ? 'text-rose-600' : 'text-slate-600'
								"
							>
								{{ date(inv.due_date) }}
							</td>
							<td class="table-cell tabular text-right font-medium">
								{{ money(inv.final_amount) }}
							</td>
							<td
								class="table-cell tabular text-right"
								:class="
									inv.docstatus === 1 && inv.outstanding_amount > 0
										? 'font-medium text-amber-700'
										: 'text-slate-400'
								"
							>
								{{ inv.docstatus === 1 ? money(inv.outstanding_amount) : "—" }}
							</td>
							<td class="table-cell"><StatusBadge :status="inv.status" /></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<InvoiceDrawer :name="selected" @close="selected = null" />
	</div>
</template>

<script setup>
import { FileText, Plus, Sparkles } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import InvoiceDrawer from "@/components/InvoiceDrawer.vue";
import PageHeader from "@/components/PageHeader.vue";
import SearchInput from "@/components/SearchInput.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Tabs from "@/components/Tabs.vue";
import { openDialog } from "@/dialogs";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { date, debounce, money } from "@/utils";

const route = useRoute();
const status = ref(route.query.status || "");
const search = ref("");
const month = ref("");
const year = ref("");
const selected = ref(route.query.invoice || null);

const { data, loading, reload } = useResource(
	() =>
		get("get_invoices", {
			status: status.value,
			search: search.value,
			billing_month: month.value,
			billing_year: year.value,
			...scope(),
		}),
	{ initial: { invoices: [], counts: {} } }
);
const invoices = computed(() => data.value?.invoices || []);
const tabs = computed(() => {
	const counts = data.value?.counts || {};
	const total = Object.values(counts).reduce((a, b) => a + b, 0);
	return [
		{ value: "", label: "All", count: total },
		...["Unpaid", "Overdue", "Partly Paid", "Paid", "Draft"].map((s) => ({
			value: s,
			label: s,
			count: counts[s] || 0,
		})),
	];
});

watch([status, month, year], reload);
watch(search, debounce(reload, 250));
</script>
