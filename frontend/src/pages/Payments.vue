<template>
	<div>
		<PageHeader title="Payments" subtitle="Rent received from tenants">
			<Button variant="primary" :icon="Plus" @click="openDialog('recordPayment')"
				>Record payment</Button
			>
		</PageHeader>

		<!-- reported by tenants in the tenant app -->
		<div v-if="toConfirm.length" class="card mb-6 border-sky-200">
			<div class="px-5 pt-4">
				<h2 class="font-semibold">To confirm</h2>
				<p class="text-sm text-slate-500">
					Tenants say they paid these. Confirm once the money has reached you.
				</p>
			</div>
			<ul class="mt-2 divide-y divide-slate-100">
				<li
					v-for="p in toConfirm"
					:key="p.name"
					class="flex flex-wrap items-center gap-3 px-5 py-3"
				>
					<div class="min-w-0 flex-1">
						<p class="font-medium">
							{{ p.tenant_name }} ·
							<span class="tabular">{{ money(p.amount) }}</span>
						</p>
						<p class="text-xs text-slate-500">
							{{ p.mode_of_payment }} · ref {{ p.reference_no || "—" }} ·
							{{ date(p.payment_date) }} · {{ p.rent_invoice }}
						</p>
					</div>
					<Button size="sm" variant="success" :icon="Check" @click="confirm(p)"
						>Confirm</Button
					>
					<Button size="sm" variant="ghost" @click="reject(p)">Not received</Button>
				</li>
			</ul>
		</div>

		<div class="mb-6 grid gap-4 sm:grid-cols-3">
			<StatCard
				label="Total shown"
				:value="money(total)"
				:hint="`${payments.length} payment${payments.length === 1 ? '' : 's'}`"
				:icon="Wallet"
				tone="green"
			/>
			<div class="card p-5 sm:col-span-2">
				<p class="text-sm font-medium text-slate-500">By mode of payment</p>
				<div class="mt-4 flex h-2.5 overflow-hidden rounded-full bg-slate-100">
					<div
						v-for="m in byMode"
						:key="m.mode"
						:class="m.color"
						:style="{ width: `${(m.amount / (total || 1)) * 100}%` }"
						:title="`${m.mode}: ${money(m.amount)}`"
					/>
				</div>
				<div class="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
					<span
						v-for="m in byMode"
						:key="m.mode"
						class="inline-flex items-center gap-2 text-slate-600"
					>
						<span class="size-2.5 rounded-full" :class="m.color" />{{ m.mode }}
						<span class="tabular font-medium text-slate-900">{{
							money(m.amount)
						}}</span>
					</span>
					<span v-if="!byMode.length" class="text-slate-400">No payments yet</span>
				</div>
			</div>
		</div>

		<div class="card">
			<div class="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
				<SearchInput
					v-model="search"
					class="sm:w-80"
					placeholder="Search tenant, invoice or reference"
				/>
				<select v-model="mode" class="input sm:w-44">
					<option value="">All modes</option>
					<option v-for="m in Object.keys(colors)" :key="m">{{ m }}</option>
				</select>
			</div>
			<div v-if="loading && !payments.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 6" :key="i" class="h-10" />
			</div>
			<EmptyState v-else-if="!payments.length" :icon="Wallet" title="No payments found" />
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Date</th>
							<th class="table-head">Tenant</th>
							<th class="table-head">Invoice</th>
							<th class="table-head">Mode</th>
							<th class="table-head">Reference</th>
							<th class="table-head text-right">Amount</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr
							v-for="p in payments"
							:key="p.name"
							class="transition hover:bg-slate-50/80"
						>
							<td class="table-cell text-slate-600">{{ date(p.payment_date) }}</td>
							<td class="table-cell">
								<RouterLink
									:to="`/tenants/${p.tenant}`"
									class="font-medium hover:underline"
									>{{ p.tenant_name }}</RouterLink
								>
								<p class="text-xs text-slate-500">{{ p.name }}</p>
							</td>
							<td class="table-cell">
								<RouterLink
									:to="{ path: '/invoices', query: { invoice: p.rent_invoice } }"
									class="text-brand-600 hover:underline"
									>{{ p.rent_invoice }}</RouterLink
								>
							</td>
							<td class="table-cell">
								<span class="inline-flex items-center gap-1.5 text-slate-700"
									><span
										class="size-2 rounded-full"
										:class="colors[p.mode_of_payment]"
									/>{{ p.mode_of_payment }}</span
								>
							</td>
							<td class="table-cell text-slate-500">{{ p.reference_no || "—" }}</td>
							<td
								class="table-cell tabular text-right font-semibold text-emerald-600"
							>
								{{ money(p.amount) }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Check, Plus, Wallet } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SearchInput from "@/components/SearchInput.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { openDialog } from "@/dialogs";
import { bumpData, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, debounce, money } from "@/utils";

const colors = {
	Cash: "bg-emerald-500",
	UPI: "bg-brand-500",
	"Bank Transfer": "bg-sky-500",
	Cheque: "bg-amber-500",
	Card: "bg-violet-500",
	"Security Deposit": "bg-slate-400",
	Other: "bg-slate-300",
};
// "Record payment" on the phone's home screen
if (useRoute().query.new) openDialog("recordPayment");

const search = ref("");
const mode = ref("");
const { data, loading, reload } = useResource(
	() => get("get_payments", { search: search.value, mode_of_payment: mode.value, ...scope() }),
	{ initial: [] }
);
const payments = computed(() => data.value || []);

const pending = useResource(() => get("get_payments_to_confirm", scope()), { initial: [] });
const toConfirm = computed(() => pending.data.value || []);
async function confirm(p) {
	try {
		await post("confirm_payment", { name: p.name });
		toast(`Payment from ${p.tenant_name} confirmed`);
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}
async function reject(p) {
	const reason = window.prompt(
		`Why is ${p.tenant_name}'s payment rejected? (optional)`,
		"Not received"
	);
	if (reason === null) return;
	try {
		await post("reject_payment", { name: p.name, reason });
		toast("Marked as not received");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}
const total = computed(() => payments.value.reduce((s, p) => s + p.amount, 0));
const byMode = computed(() =>
	Object.keys(colors)
		.map((m) => ({
			mode: m,
			color: colors[m],
			amount: payments.value
				.filter((p) => p.mode_of_payment === m)
				.reduce((s, p) => s + p.amount, 0),
		}))
		.filter((m) => m.amount)
);
watch(mode, reload);
watch(search, debounce(reload, 250));
</script>
