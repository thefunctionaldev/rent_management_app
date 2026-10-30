<template>
	<div class="card">
		<div class="flex items-center justify-between px-5 pt-5">
			<h1 class="text-lg font-semibold">Your bills</h1>
			<RouterLink to="/receipts" class="text-sm font-medium text-brand-600"
				>Rent receipts for HRA</RouterLink
			>
		</div>
		<div v-if="!data" class="space-y-3 p-5">
			<Skeleton v-for="i in 4" :key="i" class="h-12" />
		</div>
		<EmptyState v-else-if="!data.length" :icon="ReceiptText" title="No bills yet" />
		<ul v-else class="mt-2 divide-y divide-slate-100">
			<li v-for="b in data" :key="b.name">
				<RouterLink
					:to="`/invoices/${b.name}`"
					class="flex items-center gap-3 px-5 py-3.5 transition hover:bg-slate-50"
				>
					<div class="min-w-0 flex-1">
						<p class="font-medium">{{ b.billing_month }} {{ b.billing_year }}</p>
						<p class="text-xs text-slate-500">
							{{ b.name }} · due {{ date(b.due_date) }}
						</p>
					</div>
					<div class="text-right">
						<p class="tabular text-sm font-semibold">
							{{
								money(
									b.outstanding_amount > 0
										? b.outstanding_amount
										: b.final_amount
								)
							}}
						</p>
						<StatusBadge :status="b.status" />
					</div>
				</RouterLink>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ReceiptText } from "lucide-vue-next";
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

import { get, post } from "@/api";
import EmptyState from "@/components/EmptyState.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

import { call } from "../store";

const route = useRoute();
const router = useRouter();
const { data, reload } = useResource(() => get(call("get_invoices")));

// back from the Razorpay payment page: record the payment straight away
onMounted(async () => {
	const paid = route.query.paid;
	if (!paid) return;
	router.replace({ query: {} });
	try {
		const result = await post(call("check_payment"), { name: paid });
		toast(
			result.recorded
				? "Payment received. Thank you!"
				: "We'll update the bill as soon as the payment comes through"
		);
		reload();
	} catch (e) {
		toast(e.message, "error");
	}
});
</script>
