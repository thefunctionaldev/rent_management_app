<template>
	<div v-if="data" class="space-y-4">
		<div class="card p-5">
			<div class="flex items-start justify-between">
				<div>
					<RouterLink to="/invoices" class="text-sm text-slate-500">← Bills</RouterLink>
					<h1 class="mt-1 text-lg font-semibold">
						{{ inv.billing_month }} {{ inv.billing_year }}
					</h1>
					<p class="text-sm text-slate-500">
						{{ inv.name }} · {{ data.instalments.length ? "next due" : "due" }}
						{{ date(inv.next_due_date || inv.due_date) }}
					</p>
				</div>
				<StatusBadge :status="inv.status" />
			</div>
			<dl class="tabular mt-4 divide-y divide-slate-100 text-sm">
				<div class="flex justify-between py-2.5">
					<dt class="text-slate-600">
						Rent<span v-if="inv.days_stayed !== inv.total_days" class="text-slate-400">
							({{ inv.days_stayed }} of {{ inv.total_days }} days)</span
						>
					</dt>
					<dd>{{ money(inv.pro_rated_rent) }}</dd>
				</div>
				<div
					v-for="(c, i) in data.charges"
					:key="i"
					class="flex justify-between gap-3 py-2.5"
				>
					<dt class="text-slate-600">
						{{ c.charge_type }}
						<span v-if="c.description" class="block text-xs text-slate-400">{{
							c.description
						}}</span>
					</dt>
					<dd>{{ money(c.amount) }}</dd>
				</div>
				<div v-if="inv.discount_amount" class="flex justify-between py-2.5">
					<dt class="text-slate-600">Discount</dt>
					<dd class="text-emerald-600">− {{ money(inv.discount_amount) }}</dd>
				</div>
				<div v-if="inv.late_fee" class="flex justify-between py-2.5">
					<dt class="text-slate-600">Late fee</dt>
					<dd>{{ money(inv.late_fee) }}</dd>
				</div>
				<div v-if="inv.early_discount" class="flex justify-between py-2.5">
					<dt class="text-slate-600">Paid early</dt>
					<dd class="text-emerald-600">− {{ money(inv.early_discount) }}</dd>
				</div>
				<div v-if="inv.paid_amount" class="flex justify-between py-2.5">
					<dt class="text-slate-600">Paid</dt>
					<dd class="text-emerald-600">− {{ money(inv.paid_amount) }}</dd>
				</div>
				<div class="flex justify-between py-3 text-base font-semibold">
					<dt>{{ inv.outstanding_amount > 0 ? "To pay" : "Total" }}</dt>
					<dd>
						{{
							money(
								inv.outstanding_amount > 0
									? inv.outstanding_amount
									: inv.final_amount
							)
						}}
					</dd>
				</div>
			</dl>
			<a
				:href="`/api/method/rent_management.portal.download_invoice?name=${encodeURIComponent(
					inv.name
				)}`"
				class="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600"
				><Download class="size-4" /> Download PDF</a
			>
		</div>

		<div v-if="data.instalments.length" class="card p-5">
			<h2 class="font-semibold">Instalments</h2>
			<p class="text-sm text-slate-500">Your landlord agreed you can pay this in parts.</p>
			<ul class="mt-3 divide-y divide-slate-100">
				<li
					v-for="(r, i) in data.instalments"
					:key="i"
					class="flex items-center gap-3 py-2.5 text-sm"
				>
					<span class="flex-1">{{ date(r.due_date) }}</span>
					<span class="tabular font-medium">{{ money(r.amount) }}</span>
					<StatusBadge :status="r.status" />
				</li>
			</ul>
		</div>

		<div v-if="inv.outstanding_amount > 0" class="card p-5">
			<h2 class="font-semibold">
				Pay {{ money(data.pay_now) }}
				<span
					v-if="data.instalments.length && data.pay_now < inv.outstanding_amount"
					class="text-sm font-normal text-slate-500"
					>· this instalment</span
				>
			</h2>
			<p
				v-if="data.discount_now"
				class="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
			>
				You save {{ money(data.discount_now) }} for paying by
				{{ date(inv.early_discount_until) }}.
			</p>
			<p v-if="me.read_only" class="mt-2 text-sm text-amber-700">
				Online payment is paused. Please pay your landlord directly.
			</p>
			<template v-else>
				<Button
					v-if="data.online.razorpay"
					variant="primary"
					size="lg"
					class="mt-4 w-full"
					:icon="CreditCard"
					:loading="paying"
					@click="payOnline"
					>Pay online · UPI, card, netbanking</Button
				>
				<div
					v-if="data.upi_link"
					class="mt-4 rounded-xl border border-slate-200 p-4 text-center"
				>
					<img :src="data.upi_qr" alt="UPI QR code" class="mx-auto size-44" />
					<p class="mt-2 text-sm text-slate-600">
						Scan with any UPI app, or
						<a :href="data.upi_link" class="font-medium text-brand-600"
							>open your UPI app</a
						>
					</p>
					<p class="text-xs text-slate-400">{{ data.upi_id }}</p>
				</div>
			</template>

			<details
				class="mt-4 rounded-xl bg-slate-50 p-4"
				:open="!data.online.razorpay && !data.upi_link"
			>
				<summary class="cursor-pointer text-sm font-medium text-slate-700">
					Paid another way? Tell your landlord
				</summary>
				<form class="mt-3 space-y-3" @submit.prevent="report">
					<div class="grid grid-cols-2 gap-3">
						<Field label="Amount">
							<input
								v-model.number="claim.amount"
								type="number"
								min="1"
								class="input tabular"
								required
							/>
						</Field>
						<Field label="Paid by">
							<select v-model="claim.mode_of_payment" class="input">
								<option>UPI</option>
								<option>Bank Transfer</option>
								<option>Cash</option>
								<option>Cheque</option>
							</select>
						</Field>
					</div>
					<Field label="UTR / reference number">
						<input
							v-model="claim.reference_no"
							class="input"
							placeholder="From your UPI or bank app"
						/>
					</Field>
					<Button type="submit" class="w-full" :loading="reporting">I've paid</Button>
				</form>
			</details>
			<p
				v-for="p in data.pending"
				:key="p.name"
				class="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800"
			>
				You reported {{ money(p.amount) }} by {{ p.mode_of_payment }} on
				{{ date(p.payment_date) }}. Waiting for your landlord to confirm.
			</p>
		</div>

		<div v-if="data.payments.length" class="card">
			<h2 class="px-5 pt-4 font-semibold">Payments</h2>
			<ul class="mt-2 divide-y divide-slate-100">
				<li
					v-for="p in data.payments"
					:key="p.name"
					class="flex justify-between px-5 py-3 text-sm"
				>
					<div>
						<p class="font-medium">{{ p.mode_of_payment }}</p>
						<p class="text-xs text-slate-500">
							{{ date(p.payment_date)
							}}{{ p.reference_no ? ` · ${p.reference_no}` : "" }}
						</p>
					</div>
					<p class="tabular font-semibold text-emerald-600">{{ money(p.amount) }}</p>
				</li>
			</ul>
		</div>
	</div>
	<Skeleton v-else class="h-96" />
</template>

<script setup>
import { CreditCard, Download } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

import { call, me } from "../store";

const props = defineProps({ name: { type: String, required: true } });
const { data, reload } = useResource(() => get(call("get_invoice"), { name: props.name }));
const inv = computed(() => data.value?.invoice);

const claim = reactive({ amount: 0, mode_of_payment: "UPI", reference_no: "" });
watch(data, (value) => value && (claim.amount = value.pay_now), { immediate: true });

const paying = ref(false);
async function payOnline() {
	paying.value = true;
	try {
		window.location.href = await post(call("pay_online"), { name: props.name });
	} catch (e) {
		toast(e.message, "error");
		paying.value = false;
	}
}

const reporting = ref(false);
async function report() {
	reporting.value = true;
	try {
		await post(call("report_payment"), { name: props.name, ...claim });
		toast("Thanks! Your landlord will confirm the payment");
		claim.reference_no = "";
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		reporting.value = false;
	}
}
</script>
