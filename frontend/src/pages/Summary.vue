<template>
	<div>
		<PageHeader
			title="Monthly report"
			subtitle="How the month went, ready to send to the owner"
		>
			<div class="flex items-center gap-1">
				<button
					class="rounded-lg p-2 hover:bg-slate-100"
					title="Earlier"
					@click="shift(-1)"
				>
					<ChevronLeft class="size-4" />
				</button>
				<span class="w-36 text-center text-sm font-medium">{{ month }} {{ year }}</span>
				<button
					class="rounded-lg p-2 hover:bg-slate-100 disabled:opacity-30"
					title="Later"
					:disabled="isCurrentMonth"
					@click="shift(1)"
				>
					<ChevronRight class="size-4" />
				</button>
			</div>
			<Button
				v-if="data"
				variant="success"
				:icon="MessageCircle"
				:href="data.whatsapp_url"
				target="_blank"
				>Open in WhatsApp</Button
			>
			<Button v-if="data?.can_send" :icon="Send" :loading="sending" @click="send"
				>Send to owner</Button
			>
		</PageHeader>

		<div v-if="!data" class="space-y-4">
			<Skeleton class="h-28" />
			<Skeleton class="h-72" />
		</div>
		<template v-else>
			<p
				v-if="s.is_current"
				class="mb-4 rounded-xl bg-sky-50 px-4 py-3 text-sm text-sky-800"
			>
				{{ month }} isn't over yet, so this is the month so far.
			</p>

			<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Collected"
					:value="money(s.collected)"
					:hint="
						s.collection_rate !== null
							? `${s.collection_rate}% of ${money(s.invoiced)} invoiced`
							: 'Nothing invoiced'
					"
					:icon="Wallet"
					tone="green"
				/>
				<StatCard
					label="Spent"
					:value="money(s.expenses)"
					:hint="change('expenses')"
					:icon="Receipt"
					tone="amber"
				/>
				<StatCard
					label="Profit"
					:value="money(s.profit)"
					:hint="change('profit')"
					:icon="TrendingUp"
					:tone="s.profit >= 0 ? 'indigo' : 'rose'"
				/>
				<StatCard
					label="Beds taken"
					:value="`${s.taken} of ${s.beds}`"
					:hint="`${s.occupancy}% full`"
					:icon="BedDouble"
					tone="sky"
				/>
			</div>

			<div class="mt-6 grid gap-6 lg:grid-cols-[1fr_22rem]">
				<div class="space-y-6">
					<div v-if="s.buildings.length > 1" class="card overflow-x-auto">
						<table class="w-full min-w-[36rem] text-sm">
							<thead class="bg-slate-50/60">
								<tr>
									<th class="table-head">Building</th>
									<th class="table-head text-right">Collected</th>
									<th class="table-head text-right">Spent</th>
									<th class="table-head text-right">Profit</th>
									<th class="table-head text-right">Beds</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-slate-100">
								<tr v-for="b in s.buildings" :key="b.name">
									<td class="table-cell font-medium">{{ b.name }}</td>
									<td class="table-cell tabular text-right">
										{{ money(b.collected) }}
									</td>
									<td class="table-cell tabular text-right">
										{{ money(b.expenses) }}
									</td>
									<td
										class="table-cell tabular text-right font-medium"
										:class="b.profit < 0 && 'text-rose-600'"
									>
										{{ money(b.profit) }}
									</td>
									<td class="table-cell tabular text-right">
										{{ b.taken }} / {{ b.beds }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div class="card">
						<div
							class="flex items-center justify-between border-b border-slate-100 px-5 py-4"
						>
							<h3 class="font-semibold">Still to collect</h3>
							<span class="tabular font-semibold text-amber-700">{{
								money(s.outstanding)
							}}</span>
						</div>
						<p v-if="!s.defaulters.length" class="px-5 py-6 text-sm text-slate-500">
							Nobody is overdue.
						</p>
						<ul v-else class="divide-y divide-slate-100">
							<li
								v-for="d in s.defaulters"
								:key="d.tenant"
								class="flex items-center justify-between gap-3 px-5 py-3 text-sm"
							>
								<div>
									<RouterLink
										:to="`/tenants/${d.tenant}`"
										class="font-medium hover:underline"
										>{{ d.tenant_name }}</RouterLink
									>
									<p class="text-xs text-slate-500">
										Room {{ d.room }} · due since {{ date(d.since) }}
									</p>
								</div>
								<span class="tabular font-medium">{{ money(d.amount) }}</span>
							</li>
						</ul>
					</div>

					<div class="grid gap-6 md:grid-cols-2">
						<div class="card">
							<h3 class="border-b border-slate-100 px-5 py-4 font-semibold">
								Moved in
								<span class="tabular text-slate-400">{{ s.moved_in.length }}</span>
							</h3>
							<ul class="divide-y divide-slate-100 text-sm">
								<li
									v-for="m in s.moved_in"
									:key="m.tenant_name + m.allotment_date"
									class="flex justify-between px-5 py-2.5"
								>
									<span
										>{{ m.tenant_name }}
										<span class="text-slate-400">· {{ m.room }}</span></span
									>
									<span class="text-slate-500">{{
										shortDate(m.allotment_date)
									}}</span>
								</li>
								<li v-if="!s.moved_in.length" class="px-5 py-4 text-slate-500">
									Nobody
								</li>
							</ul>
						</div>
						<div class="card">
							<h3 class="border-b border-slate-100 px-5 py-4 font-semibold">
								Moved out
								<span class="tabular text-slate-400">{{
									s.moved_out.length
								}}</span>
							</h3>
							<ul class="divide-y divide-slate-100 text-sm">
								<li
									v-for="m in s.moved_out"
									:key="m.tenant_name + m.vacate_date"
									class="flex justify-between px-5 py-2.5"
								>
									<span
										>{{ m.tenant_name }}
										<span class="text-slate-400">· {{ m.room }}</span></span
									>
									<span class="text-slate-500">{{
										shortDate(m.vacate_date)
									}}</span>
								</li>
								<li v-if="!s.moved_out.length" class="px-5 py-4 text-slate-500">
									Nobody
								</li>
							</ul>
						</div>
					</div>
				</div>

				<div class="space-y-6">
					<div class="card p-5">
						<h3 class="font-semibold">Where the money went</h3>
						<p v-if="!s.top_expenses.length" class="mt-2 text-sm text-slate-500">
							No expenses this month.
						</p>
						<ul class="mt-3 space-y-2.5 text-sm">
							<li v-for="c in s.top_expenses" :key="c.category">
								<div class="flex justify-between">
									<span>{{ c.category }}</span>
									<span class="tabular">{{ money(c.amount) }}</span>
								</div>
								<div class="mt-1 h-1.5 rounded-full bg-slate-100">
									<div
										class="h-1.5 rounded-full bg-amber-400"
										:style="{
											width: `${Math.round((c.amount / s.expenses) * 100)}%`,
										}"
									/>
								</div>
							</li>
						</ul>
					</div>

					<div class="card space-y-2 p-5 text-sm">
						<h3 class="font-semibold">Also this month</h3>
						<p class="flex justify-between">
							<span class="text-slate-500">New enquiries</span>
							<span class="tabular">{{ s.enquiries }}</span>
						</p>
						<p class="flex justify-between">
							<span class="text-slate-500">Requests raised</span>
							<span class="tabular">{{ s.requests_opened }}</span>
						</p>
						<p class="flex justify-between">
							<span class="text-slate-500">Requests still open</span>
							<span class="tabular">{{ s.requests_open }}</span>
						</p>
						<p class="flex justify-between">
							<span class="text-slate-500">Leaving in the next 30 days</span>
							<span class="tabular">{{ s.leaving.length }}</span>
						</p>
					</div>

					<div class="card p-5">
						<h3 class="font-semibold">The message</h3>
						<pre
							class="mt-3 rounded-xl bg-slate-50 p-3 font-sans text-xs whitespace-pre-wrap text-slate-700"
							>{{ data.text }}</pre
						>
						<p class="mt-3 text-xs text-slate-500">
							<template v-if="data.last_sent"
								>Last sent {{ date(data.last_sent.creation.slice(0, 10)) }} by
								{{ data.last_sent.channel }} to
								{{ data.last_sent.recipient }}.</template
							>
							<RouterLink to="/settings" class="text-brand-600 hover:underline">
								Send it automatically every month</RouterLink
							>
						</p>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import {
	BedDouble,
	ChevronLeft,
	ChevronRight,
	MessageCircle,
	Receipt,
	Send,
	TrendingUp,
	Wallet,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { boot, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const route = useRoute();
const today = new Date(`${boot.today}T00:00:00`);
// last month, or the one in the link from the owner's message
const fromLink = route.query.month && boot.months.indexOf(route.query.month);
const cursor = ref(
	fromLink >= 0 && route.query.year
		? new Date(Number(route.query.year), fromLink, 1)
		: new Date(today.getFullYear(), today.getMonth() - 1, 1)
);
const month = computed(() => boot.months[cursor.value.getMonth()]);
const year = computed(() => cursor.value.getFullYear());
const isCurrentMonth = computed(
	() =>
		cursor.value.getFullYear() === today.getFullYear() &&
		cursor.value.getMonth() === today.getMonth()
);
const shift = (n) =>
	(cursor.value = new Date(cursor.value.getFullYear(), cursor.value.getMonth() + n, 1));

const { data, reload } = useResource(() =>
	get("get_owner_summary", { month: month.value, year: year.value, ...scope() })
);
watch(cursor, reload);
const s = computed(() => data.value?.summary);

function change(field) {
	const before = s.value.previous[field];
	if (!before) return `${s.value.previous.label}: ${money(0)}`;
	const pct = Math.round(((s.value[field] - before) / Math.abs(before)) * 100);
	return `${pct >= 0 ? "+" : ""}${pct}% vs ${s.value.previous.label}`;
}

const sending = ref(false);
async function send() {
	sending.value = true;
	try {
		const statuses = await post("send_owner_summary", {
			month: month.value,
			year: year.value,
		});
		toast(
			statuses.includes("Sent")
				? "Sent to the owner"
				: "It couldn't be sent. Check WhatsApp and email in Settings",
			statuses.includes("Sent") ? "success" : "error"
		);
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		sending.value = false;
	}
}
</script>
