<template>
	<div>
		<PageHeader
			title="Security deposits"
			subtitle="Collect deposits at move-in and settle them at move-out"
		/>

		<div class="mb-6 grid gap-4 sm:grid-cols-3">
			<StatCard
				label="Deposits held"
				:value="money(heldTotal)"
				:hint="`${collected.length} active tenant${collected.length === 1 ? '' : 's'}`"
				:icon="ShieldCheck"
			/>
			<StatCard
				label="Yet to collect"
				:value="money(uncollectedTotal)"
				:hint="`${uncollected.length} tenant${uncollected.length === 1 ? '' : 's'}`"
				:icon="Hourglass"
				tone="amber"
			/>
			<StatCard
				label="Awaiting settlement"
				:value="String(pending.length)"
				hint="Tenants who have moved out"
				:icon="LogOut"
				tone="sky"
			/>
		</div>

		<section class="mb-8">
			<h2 class="mb-3 text-sm font-semibold text-slate-900">Awaiting settlement</h2>
			<div v-if="pending.length" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
				<div v-for="a in pending" :key="a.name" class="card p-5">
					<div class="flex items-center gap-3">
						<Avatar :name="a.tenant_name" :image="a.tenant_picture" />
						<div class="min-w-0 flex-1">
							<p class="truncate font-medium">{{ a.tenant_name }}</p>
							<p class="text-xs text-slate-500">
								Room {{ a.room }} · moved out {{ date(a.vacate_date) }}
							</p>
						</div>
					</div>
					<div class="mt-4 flex items-end justify-between">
						<div>
							<p class="text-xs text-slate-500">Deposit</p>
							<p class="tabular text-xl font-semibold">
								{{ money(a.security_deposit) }}
							</p>
						</div>
						<Button
							v-if="a.deposit_collected"
							variant="primary"
							size="sm"
							:icon="ShieldCheck"
							@click="openDialog('settleDeposit', { allotment: a })"
							>Settle</Button
						>
						<Button
							v-else
							size="sm"
							@click="openDialog('collectDeposit', { allotment: a })"
							>Mark collected first</Button
						>
					</div>
				</div>
			</div>
			<div v-else class="card">
				<EmptyState
					:icon="ShieldCheck"
					title="Nothing to settle"
					description="Deposits show up here after a tenant vacates."
				/>
			</div>
		</section>

		<section class="mb-8">
			<h2 class="mb-3 text-sm font-semibold text-slate-900">Current tenants</h2>
			<div class="card overflow-x-auto">
				<EmptyState v-if="!held.length" :icon="ShieldCheck" title="No deposits" />
				<table v-else class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Tenant</th>
							<th class="table-head">Room</th>
							<th class="table-head">Since</th>
							<th class="table-head">Status</th>
							<th class="table-head text-right">Deposit</th>
							<th class="table-head"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr v-for="a in held" :key="a.name">
							<td class="table-cell">
								<RouterLink
									:to="`/tenants/${a.tenant}`"
									class="font-medium hover:underline"
									>{{ a.tenant_name }}</RouterLink
								>
							</td>
							<td class="table-cell text-slate-600">{{ a.room }}</td>
							<td class="table-cell text-slate-600">{{ date(a.allotment_date) }}</td>
							<td class="table-cell">
								<span
									v-if="a.deposit_collected"
									class="inline-flex items-center gap-1 text-sm text-emerald-600"
									><Check class="size-4" />Collected
									{{ shortDate(a.deposit_collected_on) }}</span
								>
								<span v-else class="text-sm text-amber-600">Not collected</span>
							</td>
							<td class="table-cell tabular text-right font-medium">
								{{ money(a.security_deposit) }}
							</td>
							<td class="table-cell text-right">
								<Button
									v-if="!a.deposit_collected"
									size="sm"
									@click="openDialog('collectDeposit', { allotment: a })"
									>Mark collected</Button
								>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<section>
			<h2 class="mb-3 text-sm font-semibold text-slate-900">Settled</h2>
			<div class="card overflow-x-auto">
				<EmptyState
					v-if="!settlements.length"
					:icon="ShieldCheck"
					title="No settlements yet"
				/>
				<table v-else class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Tenant</th>
							<th class="table-head">Date</th>
							<th class="table-head text-right">Deposit</th>
							<th class="table-head text-right">Deductions</th>
							<th class="table-head text-right">Rent adjusted</th>
							<th class="table-head text-right">Refunded</th>
							<th class="table-head text-right">Still owed</th>
						</tr>
					</thead>
					<tbody class="tabular divide-y divide-slate-100">
						<tr v-for="s in settlements" :key="s.name">
							<td class="table-cell">
								<p class="font-medium">{{ s.tenant_name }}</p>
								<p class="text-xs text-slate-500">
									{{ s.name }} · Room {{ s.room }}
								</p>
							</td>
							<td class="table-cell text-slate-600">
								{{ date(s.settlement_date) }}
							</td>
							<td class="table-cell text-right">{{ money(s.security_deposit) }}</td>
							<td class="table-cell text-right text-slate-600">
								{{ money(s.total_deductions) }}
							</td>
							<td class="table-cell text-right text-slate-600">
								{{ money(s.rent_adjusted) }}
							</td>
							<td class="table-cell text-right font-semibold text-emerald-600">
								{{ money(s.refund_amount) }}
							</td>
							<td
								class="table-cell text-right"
								:class="
									s.balance_payable_by_tenant
										? 'font-semibold text-rose-600'
										: 'text-slate-400'
								"
							>
								{{
									s.balance_payable_by_tenant
										? money(s.balance_payable_by_tenant)
										: "—"
								}}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>
	</div>
</template>

<script setup>
import { Check, Hourglass, LogOut, ShieldCheck } from "lucide-vue-next";
import { computed } from "vue";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import StatCard from "@/components/StatCard.vue";
import { openDialog } from "@/dialogs";
import { scope } from "@/store";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const { data } = useResource(() => get("get_deposits", scope()), {
	initial: { pending: [], held: [], settlements: [] },
});
const pending = computed(() => data.value?.pending || []);
const held = computed(() => data.value?.held || []);
const settlements = computed(() => data.value?.settlements || []);
const collected = computed(() => held.value.filter((a) => a.deposit_collected));
const uncollected = computed(() => held.value.filter((a) => !a.deposit_collected));
const sum = (rows) => rows.reduce((s, a) => s + a.security_deposit, 0);
const heldTotal = computed(() => sum(collected.value));
const uncollectedTotal = computed(() => sum(uncollected.value));
</script>
