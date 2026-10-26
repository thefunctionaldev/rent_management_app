<template>
	<div>
		<PageHeader
			title="Your business"
			subtitle="Every customer site, from their daily heartbeat"
		>
			<Button :icon="ExternalLink" href="/app/saas-signup" target="_blank">Signups</Button>
		</PageHeader>

		<template v-if="d">
			<div class="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Monthly recurring revenue"
					:value="money(d.mrr)"
					:hint="`${money(d.arr)} a year`"
					:icon="TrendingUp"
				/>
				<StatCard
					label="Paying customers"
					:value="d.paying"
					:hint="`${d.customers} sites in total`"
					:icon="Users"
					tone="green"
				/>
				<StatCard
					label="Trial to paid"
					:value="d.conversion === null ? '—' : `${d.conversion}%`"
					hint="of trials that have ended"
					:icon="Sparkles"
					tone="sky"
				/>
				<StatCard
					label="Collected so far"
					:value="money(d.revenue_total)"
					:icon="Wallet"
					tone="amber"
				/>
			</div>

			<div class="mb-6 grid gap-4 lg:grid-cols-3">
				<div class="card p-5">
					<h2 class="font-semibold">Customers by status</h2>
					<ul class="mt-3 space-y-2 text-sm">
						<li
							v-for="s in statuses"
							:key="s"
							class="flex items-center justify-between"
						>
							<StatusBadge :status="s" />
							<span class="tabular font-medium">{{ d.by_status[s] || 0 }}</span>
						</li>
					</ul>
				</div>
				<div class="card p-5">
					<h2 class="font-semibold">New sites</h2>
					<div class="mt-4 flex h-32 items-end gap-3">
						<div
							v-for="m in d.signups"
							:key="m.month"
							class="flex flex-1 flex-col items-center gap-1"
						>
							<span class="tabular text-xs text-slate-500">{{ m.count }}</span>
							<div
								class="w-full rounded-t-md bg-brand-500"
								:style="{
									height: `${(m.count / maxSignups) * 90}px`,
									minHeight: m.count ? '4px' : '1px',
								}"
							/>
							<span class="text-[11px] text-slate-500">{{ m.month }}</span>
						</div>
					</div>
				</div>
				<div class="card p-5">
					<h2 class="font-semibold">Needs attention</h2>
					<ul class="mt-3 space-y-2 text-sm">
						<li
							v-for="a in attention"
							:key="a.label"
							class="flex items-center justify-between"
						>
							<span class="text-slate-600">{{ a.label }}</span>
							<span
								class="tabular font-medium"
								:class="a.count ? a.tone : 'text-slate-400'"
								>{{ a.count }}</span
							>
						</li>
					</ul>
				</div>
			</div>

			<div v-if="followUps.length" class="card mb-6">
				<h2 class="px-5 pt-4 font-semibold">Follow up this week</h2>
				<ul class="mt-2 divide-y divide-slate-100">
					<li
						v-for="c in followUps"
						:key="c.site + c.reason"
						class="flex flex-wrap items-center gap-3 px-5 py-3 text-sm"
					>
						<div class="min-w-0 flex-1">
							<p class="font-medium">{{ c.billing_name || c.site }}</p>
							<p class="text-xs text-slate-500">
								{{ c.site }} · {{ c.contact_email || "no email" }} ·
								{{ c.contact_phone || "no phone" }}
							</p>
						</div>
						<span class="text-xs font-medium" :class="c.tone">{{ c.reason }}</span>
						<a
							v-if="c.contact_phone"
							:href="`https://wa.me/${c.contact_phone.replace(/\D/g, '')}`"
							target="_blank"
							class="text-brand-600"
							><MessageCircle class="size-4"
						/></a>
					</li>
				</ul>
			</div>

			<div class="card">
				<div
					class="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between"
				>
					<h2 class="font-semibold">All customers</h2>
					<SearchInput
						v-model="search"
						class="sm:w-72"
						placeholder="Search site, business or email"
					/>
				</div>
				<div class="overflow-x-auto">
					<table class="w-full">
						<thead class="border-b border-slate-100 bg-slate-50/60">
							<tr>
								<th class="table-head">Customer</th>
								<th class="table-head">Status</th>
								<th class="table-head">Plan</th>
								<th class="table-head">Until</th>
								<th class="table-head text-right">Beds</th>
								<th class="table-head text-right">MRR</th>
								<th class="table-head">Last seen</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100">
							<tr v-for="c in customers" :key="c.site">
								<td class="table-cell">
									<a
										:href="`https://${c.site}/rent`"
										target="_blank"
										class="font-medium hover:underline"
										>{{ c.billing_name || c.site }}</a
									>
									<p class="text-xs text-slate-500">{{ c.site }}</p>
								</td>
								<td class="table-cell"><StatusBadge :status="c.status" /></td>
								<td class="table-cell text-slate-600">
									{{ c.plan
									}}<span v-if="c.billing_cycle" class="text-xs text-slate-400">
										· {{ c.billing_cycle }}</span
									>
									<span v-if="c.auto_renew" class="ml-1 text-xs text-emerald-600"
										>auto</span
									>
								</td>
								<td class="table-cell text-slate-600">
									{{ date(c.current_period_end || c.trial_ends_on) }}
								</td>
								<td class="table-cell tabular text-right">{{ c.beds }}</td>
								<td class="table-cell tabular text-right font-medium">
									{{ money(c.mrr) }}
								</td>
								<td class="table-cell text-xs text-slate-500">
									{{
										c.last_seen ? shortDate(c.last_seen.slice(0, 10)) : "never"
									}}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</template>
		<Skeleton v-else class="h-96" />
	</div>
</template>

<script setup>
import { ExternalLink, MessageCircle, Sparkles, TrendingUp, Users, Wallet } from "lucide-vue-next";
import { computed, ref } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import PageHeader from "@/components/PageHeader.vue";
import SearchInput from "@/components/SearchInput.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const { data } = useResource(() => get("rent_management.saas.get_dashboard"));
const d = data;
const statuses = ["Trial", "Active", "Past Due", "Expired"];
const search = ref("");
const maxSignups = computed(() => Math.max(1, ...(d.value?.signups || []).map((m) => m.count)));
const attention = computed(() => [
	{
		label: "Trials ending in 7 days",
		count: d.value.trials_ending.length,
		tone: "text-sky-700",
	},
	{
		label: "Renewals due in 7 days (no auto-renew)",
		count: d.value.renewals_due.length,
		tone: "text-amber-700",
	},
	{ label: "Past due", count: d.value.past_due.length, tone: "text-rose-700" },
	{ label: "No heartbeat for 2 days", count: d.value.silent.length, tone: "text-rose-700" },
	{ label: "Signups to look at", count: d.value.pending_signups, tone: "text-amber-700" },
]);
const followUps = computed(() => [
	...d.value.trials_ending.map((c) => ({
		...c,
		reason: `Trial ends ${shortDate(c.trial_ends_on)}`,
		tone: "text-sky-700",
	})),
	...d.value.renewals_due.map((c) => ({
		...c,
		reason: `Renewal due ${shortDate(c.current_period_end)}`,
		tone: "text-amber-700",
	})),
	...d.value.past_due.map((c) => ({ ...c, reason: "Past due", tone: "text-rose-700" })),
]);
const customers = computed(() => {
	const q = search.value.toLowerCase();
	return d.value.list.filter(
		(c) =>
			!q ||
			[c.site, c.billing_name, c.contact_email].some((v) =>
				(v || "").toLowerCase().includes(q)
			)
	);
});
</script>
