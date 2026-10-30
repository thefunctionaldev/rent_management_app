<template>
	<div class="p-5">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<p class="text-sm text-slate-500">
				For the tenant's employer (HRA): rent only, with the landlord's PAN.
			</p>
			<select v-if="data" v-model="fy" class="input w-44 py-1.5" @change="load">
				<option v-for="y in data.years" :key="y" :value="y">FY {{ y }}</option>
			</select>
		</div>
		<Skeleton v-if="!data" class="mt-4 h-24" />
		<template v-else>
			<p
				v-if="data.pan_missing"
				class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
			>
				Over ₹1,00,000 this year: add the landlord's PAN in Settings (or the owner's on the
				building) so their employer accepts the receipts.
			</p>
			<p v-if="!data.months.length" class="mt-4 text-sm text-slate-500">
				No rent paid in this year.
			</p>
			<ul v-else class="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
				<li
					v-for="m in data.months"
					:key="m.invoice"
					class="flex items-center gap-3 px-4 py-2.5 text-sm"
				>
					<span class="flex-1">{{ m.label }}</span>
					<span class="tabular">{{ money(m.paid) }}</span>
					<a :href="link(m.invoice)" class="text-brand-600 hover:underline">PDF</a>
				</li>
			</ul>
			<Button v-if="data.months.length" class="mt-3" :icon="Download" :href="link()"
				>Whole year · {{ money(data.total) }}</Button
			>
		</template>
	</div>
</template>

<script setup>
import { Download } from "lucide-vue-next";
import { ref } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import Skeleton from "@/components/Skeleton.vue";
import { money } from "@/utils";

const props = defineProps({ tenant: { type: [String, Number], required: true } });
const data = ref(null);
const fy = ref("");
async function load() {
	data.value = await get("get_rent_receipts", {
		tenant: props.tenant,
		...(fy.value && { fy: fy.value }),
	});
	fy.value = data.value.fy;
}
load();
const link = (invoice) =>
	`/api/method/rent_management.api.download_rent_receipt?tenant=${encodeURIComponent(
		props.tenant
	)}&fy=${encodeURIComponent(fy.value)}${
		invoice ? `&invoice=${encodeURIComponent(invoice)}` : ""
	}`;
</script>
