<template>
	<div class="space-y-4">
		<div class="card p-5">
			<RouterLink to="/invoices" class="text-sm text-slate-500">← Bills</RouterLink>
			<h1 class="mt-1 text-lg font-semibold">Rent receipts</h1>
			<p class="text-sm text-slate-500">
				For your employer, to claim HRA. They show only the rent you paid, with your
				landlord's PAN.
			</p>
			<select
				v-if="data"
				v-model="fy"
				class="input mt-4"
				aria-label="Financial year"
				@change="load"
			>
				<option v-for="y in data.years" :key="y" :value="y">Financial year {{ y }}</option>
			</select>
		</div>

		<div v-if="!data" class="card h-48 animate-pulse bg-slate-100" />
		<template v-else>
			<p
				v-if="data.pan_missing"
				class="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
			>
				Your rent this year is over ₹1,00,000, so your employer will ask for your
				landlord's PAN. It isn't on the receipts yet: ask your landlord to add it.
			</p>
			<div class="card">
				<div class="flex items-center justify-between px-5 pt-4">
					<h2 class="font-semibold">{{ data.fy }}</h2>
					<span class="tabular text-sm font-medium">{{ money(data.total) }}</span>
				</div>
				<p v-if="!data.months.length" class="px-5 py-6 text-sm text-slate-500">
					No rent paid in this year yet.
				</p>
				<ul v-else class="mt-2 divide-y divide-slate-100">
					<li
						v-for="m in data.months"
						:key="m.invoice"
						class="flex items-center gap-3 px-5 py-3"
					>
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">{{ m.label }}</p>
							<p class="text-xs text-slate-500">
								{{ money(m.paid)
								}}<template v-if="!m.fully_paid"> of {{ money(m.rent) }}</template>
								<template v-if="m.paid_on"> · paid {{ date(m.paid_on) }}</template>
							</p>
						</div>
						<a
							:href="link(m.invoice)"
							class="rounded-lg p-2 text-brand-600 hover:bg-brand-50"
							title="Download"
						>
							<Download class="size-5" />
						</a>
					</li>
				</ul>
				<div v-if="data.months.length" class="p-5 pt-2">
					<Button
						variant="primary"
						size="lg"
						class="w-full"
						:icon="Download"
						:href="link()"
						>Receipt for the whole year</Button
					>
				</div>
			</div>
			<p class="px-1 text-xs text-slate-400">
				Paid to {{ data.payee.name
				}}<template v-if="data.payee.pan"> · PAN {{ data.payee.pan }}</template>
			</p>
		</template>
	</div>
</template>

<script setup>
import { Download } from "lucide-vue-next";
import { ref } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import { date, money } from "@/utils";

import { call } from "../store";

const data = ref(null);
const fy = ref("");
async function load() {
	data.value = await get(call("get_rent_receipts"), fy.value ? { fy: fy.value } : {});
	fy.value = data.value.fy;
}
load();

const link = (invoice) =>
	`/api/method/${call("download_rent_receipt")}?fy=${encodeURIComponent(fy.value)}${
		invoice ? `&invoice=${encodeURIComponent(invoice)}` : ""
	}`;
</script>
