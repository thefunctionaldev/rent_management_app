<template>
	<div>
		<PageHeader title="Outstanding rent" subtitle="Who owes what, and for how long">
			<label class="flex items-center gap-2 text-sm text-slate-600">
				<input v-model="overdueOnly" type="checkbox" class="size-4 accent-brand-600" />
				Overdue only
			</label>
			<input v-model="asOn" type="date" class="input w-auto" title="As on date" />
			<Button variant="primary" :icon="Send" @click="openDialog('remindAll')"
				>Remind all</Button
			>
		</PageHeader>

		<div class="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
			<button
				v-for="(b, i) in buckets"
				:key="b.fieldname"
				class="card p-4 text-left transition hover:shadow-md"
				:class="bucket === b.fieldname && 'ring-2 ring-brand-500'"
				@click="bucket = bucket === b.fieldname ? '' : b.fieldname"
			>
				<p class="text-xs font-medium text-slate-500">{{ b.label }}</p>
				<p
					class="tabular mt-1 text-lg font-semibold"
					:class="b.amount ? bucketText[i] : 'text-slate-300'"
				>
					{{ money(b.amount) }}
				</p>
				<div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
					<div
						class="h-full rounded-full"
						:class="bucketBar[i]"
						:style="{ width: `${(b.amount / maxBucket) * 100}%` }"
					/>
				</div>
			</button>
		</div>

		<div class="mt-6 card">
			<div
				class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4"
			>
				<p class="text-sm text-slate-500">
					<span class="tabular font-semibold text-slate-900">{{
						money(totalShown)
					}}</span>
					across {{ rows.length }} invoice{{ rows.length === 1 ? "" : "s" }}
					<span v-if="bucket"
						>· filtered to
						{{ buckets.find((b) => b.fieldname === bucket)?.label }}</span
					>
				</p>
			</div>
			<div v-if="loading && !data" class="space-y-3 p-5">
				<Skeleton v-for="i in 5" :key="i" class="h-10" />
			</div>
			<EmptyState
				v-else-if="!rows.length"
				:icon="PartyPopper"
				title="All clear"
				description="No outstanding rent for this selection."
			/>
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Tenant</th>
							<th class="table-head">Period</th>
							<th class="table-head">Due</th>
							<th class="table-head text-right">Days late</th>
							<th class="table-head text-right">Outstanding</th>
							<th class="table-head"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr
							v-for="r in rows"
							:key="r.name"
							class="transition hover:bg-slate-50/80"
						>
							<td class="table-cell">
								<RouterLink
									:to="`/tenants/${r.tenant}`"
									class="font-medium hover:underline"
									>{{ r.tenant_name }}</RouterLink
								>
								<p class="text-xs text-slate-500">
									Room {{ r.room }} · {{ r.mobile_no || "no phone" }}
								</p>
							</td>
							<td class="table-cell text-slate-600">{{ r.billing_period }}</td>
							<td class="table-cell text-slate-600">{{ date(r.due_date) }}</td>
							<td class="table-cell tabular text-right">
								<span
									v-if="r.days_overdue"
									class="rounded-md px-2 py-0.5 text-xs font-semibold"
									:class="
										r.days_overdue > 60
											? 'bg-rose-100 text-rose-700'
											: r.days_overdue > 30
											? 'bg-orange-100 text-orange-700'
											: 'bg-amber-100 text-amber-700'
									"
									>{{ r.days_overdue }}d</span
								>
								<span v-else class="text-xs text-slate-400">not due</span>
							</td>
							<td class="table-cell tabular text-right font-semibold">
								{{ money(r.outstanding_amount) }}
							</td>
							<td class="table-cell text-right">
								<div class="flex justify-end gap-1.5">
									<Button
										v-if="reminder(r)"
										size="sm"
										variant="ghost"
										:href="reminder(r)"
										target="_blank"
										:icon="MessageCircle"
										title="Remind on WhatsApp"
									/>
									<Button
										size="sm"
										@click="openDialog('recordPayment', { invoice: r })"
										>Collect</Button
									>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { MessageCircle, PartyPopper, Send } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import { openDialog } from "@/dialogs";
import { boot, scope } from "@/store";
import { useResource } from "@/useResource";
import { date, money, whatsappReminder } from "@/utils";

const asOn = ref(boot.today);
const overdueOnly = ref(false);
const bucket = ref("");

const { data, loading, reload } = useResource(() =>
	get("get_outstanding", {
		as_on_date: asOn.value,
		overdue_only: overdueOnly.value ? 1 : 0,
		...scope(),
	})
);
watch([asOn, overdueOnly], reload);

const bucketBar = ["bg-sky-400", "bg-amber-400", "bg-orange-400", "bg-rose-400", "bg-rose-600"];
const bucketText = [
	"text-slate-900",
	"text-amber-700",
	"text-orange-700",
	"text-rose-600",
	"text-rose-700",
];
const buckets = computed(() => data.value?.buckets || []);
const maxBucket = computed(() => Math.max(1, ...buckets.value.map((b) => b.amount)));
const rows = computed(() =>
	(data.value?.rows || []).filter((r) => !bucket.value || r[bucket.value] > 0)
);
const totalShown = computed(() => rows.value.reduce((s, r) => s + r.outstanding_amount, 0));

const reminder = (r) => whatsappReminder(r.mobile_no, r);
</script>
