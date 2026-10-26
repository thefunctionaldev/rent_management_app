<template>
	<Drawer :open="!!name" @close="$emit('close')">
		<div class="flex items-center justify-between border-b border-slate-100 px-6 py-4">
			<div>
				<p class="text-xs font-medium text-slate-500">Rent invoice</p>
				<p class="font-semibold">{{ name }}</p>
			</div>
			<button
				class="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
				@click="$emit('close')"
			>
				<X class="size-5" />
			</button>
		</div>

		<div v-if="!data" class="space-y-4 p-6">
			<Skeleton class="h-24" /><Skeleton class="h-48" />
		</div>

		<div v-else class="flex-1 overflow-y-auto px-6 py-5">
			<div class="flex items-start justify-between">
				<div class="flex items-center gap-3">
					<Avatar :name="inv.tenant_name" />
					<div>
						<RouterLink
							:to="`/tenants/${inv.tenant}`"
							class="font-semibold hover:underline"
							@click="$emit('close')"
							>{{ inv.tenant_name }}</RouterLink
						>
						<p class="text-sm text-slate-500">
							Room {{ inv.room }} · {{ inv.billing_month }} {{ inv.billing_year }}
						</p>
					</div>
				</div>
				<StatusBadge :status="inv.status" />
			</div>

			<div class="mt-5 grid grid-cols-3 gap-3 text-center">
				<div class="rounded-xl bg-slate-50 p-3">
					<p class="text-[11px] text-slate-500 uppercase">Period</p>
					<p class="mt-1 text-sm font-medium">
						{{ shortDate(inv.from_date) }} – {{ shortDate(inv.to_date) }}
					</p>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<p class="text-[11px] text-slate-500 uppercase">Days</p>
					<p class="tabular mt-1 text-sm font-medium">
						{{ inv.days_stayed }} / {{ inv.total_days }}
					</p>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<p class="text-[11px] text-slate-500 uppercase">Due</p>
					<p
						class="mt-1 text-sm font-medium"
						:class="inv.status === 'Overdue' && 'text-rose-600'"
					>
						{{ date(inv.due_date) }}
					</p>
				</div>
			</div>

			<div class="mt-5 rounded-xl border border-slate-200">
				<dl class="tabular divide-y divide-slate-100 text-sm">
					<div class="flex justify-between px-4 py-3">
						<dt class="text-slate-600">
							Rent
							<span class="text-slate-400">({{ money(inv.monthly_rent) }}/mo)</span>
						</dt>
						<dd>{{ money(inv.pro_rated_rent) }}</dd>
					</div>
					<div
						v-for="(c, i) in inv.charges"
						:key="i"
						class="flex justify-between px-4 py-3"
					>
						<dt class="text-slate-600">
							{{ c.charge_type
							}}<span v-if="c.description" class="text-slate-400">
								· {{ c.description }}</span
							>
						</dt>
						<dd>{{ money(c.amount) }}</dd>
					</div>
					<div v-if="inv.discount_amount" class="flex justify-between px-4 py-3">
						<dt class="text-slate-600">Discount</dt>
						<dd class="text-emerald-600">− {{ money(inv.discount_amount) }}</dd>
					</div>
					<div class="flex justify-between bg-slate-50/70 px-4 py-3 font-semibold">
						<dt>Total</dt>
						<dd>{{ money(inv.final_amount) }}</dd>
					</div>
					<div v-if="inv.paid_amount" class="flex justify-between px-4 py-3">
						<dt class="text-slate-600">Paid</dt>
						<dd class="text-emerald-600">− {{ money(inv.paid_amount) }}</dd>
					</div>
					<div
						v-if="inv.docstatus === 1"
						class="flex justify-between px-4 py-3 text-base font-semibold"
					>
						<dt>Balance due</dt>
						<dd
							:class="
								inv.outstanding_amount > 0 ? 'text-amber-700' : 'text-emerald-600'
							"
						>
							{{ money(inv.outstanding_amount) }}
						</dd>
					</div>
				</dl>
			</div>

			<div v-if="data.payments.length" class="mt-6">
				<h3 class="text-sm font-semibold">Payments</h3>
				<ul class="mt-2 space-y-2">
					<li
						v-for="p in data.payments"
						:key="p.name"
						class="flex items-center gap-3 rounded-xl border border-slate-100 px-3 py-2.5"
					>
						<span
							class="grid size-7 place-items-center rounded-full bg-emerald-50 text-emerald-600"
							><Check class="size-4"
						/></span>
						<div class="flex-1 text-sm">
							<p class="font-medium">
								{{ p.mode_of_payment
								}}<span v-if="p.reference_no" class="font-normal text-slate-400">
									· {{ p.reference_no }}</span
								>
							</p>
							<p class="text-xs text-slate-500">
								{{ date(p.payment_date) }} · {{ p.name }}
							</p>
						</div>
						<p class="tabular text-sm font-semibold">{{ money(p.amount) }}</p>
					</li>
				</ul>
			</div>
			<!-- online payment -->
			<div
				v-if="
					inv.docstatus === 1 &&
					inv.outstanding_amount > 0 &&
					(data.upi_qr || data.online.razorpay)
				"
				class="mt-6 rounded-xl border border-dashed border-slate-300 p-4"
			>
				<h3 class="text-sm font-semibold">Collect online</h3>
				<div class="mt-3 flex gap-4">
					<img
						v-if="data.upi_qr"
						:src="data.upi_qr"
						alt="UPI QR code"
						class="size-28 shrink-0 rounded-lg border border-slate-100"
					/>
					<div class="min-w-0 flex-1 space-y-2 text-sm">
						<p v-if="data.upi_qr" class="text-slate-600">
							The tenant scans this with any UPI app;
							{{ money(inv.outstanding_amount) }}
							is filled in. It's also printed on the invoice.
						</p>
						<template v-if="data.online.razorpay">
							<div v-if="link" class="flex items-center gap-2">
								<a
									:href="link"
									target="_blank"
									class="truncate font-medium text-brand-600 hover:underline"
									>{{ link }}</a
								>
								<button
									class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
									title="Copy link"
									@click="copyLink"
								>
									<Copy class="size-4" />
								</button>
							</div>
							<div class="flex flex-wrap gap-2">
								<Button
									v-if="!link"
									size="sm"
									:icon="Link2"
									:loading="linking.loading.value"
									@click="makeLink"
									>Create payment link</Button
								>
								<Button
									v-if="inv.payment_link_id"
									size="sm"
									variant="ghost"
									:icon="RefreshCw"
									:loading="checking.loading.value"
									@click="checkPayment"
									>Check payment</Button
								>
							</div>
						</template>
					</div>
				</div>
			</div>

			<p v-if="inv.remarks" class="mt-6 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
				{{ inv.remarks }}
			</p>
		</div>

		<div
			v-if="data"
			class="flex flex-wrap gap-2 border-t border-slate-100 bg-slate-50/60 px-6 py-4"
		>
			<template v-if="inv.docstatus === 0">
				<Button
					variant="primary"
					:icon="Send"
					:loading="submitting.loading.value"
					@click="submit"
					>Submit invoice</Button
				>
				<Button
					variant="ghost"
					:icon="Trash2"
					:loading="deleting.loading.value"
					@click="remove"
					>Delete draft</Button
				>
			</template>
			<template v-else>
				<Button
					v-if="inv.outstanding_amount > 0"
					variant="success"
					:icon="Wallet"
					@click="openDialog('recordPayment', { invoice: inv })"
					>Record payment</Button
				>
				<Button
					v-if="inv.outstanding_amount > 0"
					:icon="BellRing"
					:loading="reminding.loading.value"
					@click="remind"
					>Send reminder</Button
				>
				<Button
					v-if="reminder && inv.outstanding_amount > 0"
					variant="ghost"
					:href="reminder"
					target="_blank"
					:icon="MessageCircle"
					title="Open WhatsApp with a reminder you can edit"
					>WhatsApp</Button
				>
			</template>
			<Button
				variant="ghost"
				:href="data.print_url"
				target="_blank"
				:icon="Printer"
				class="ml-auto"
				>Print</Button
			>
		</div>
	</Drawer>
</template>

<script setup>
import {
	BellRing,
	Check,
	Copy,
	Link2,
	MessageCircle,
	Printer,
	RefreshCw,
	Send,
	Trash2,
	Wallet,
	X,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import Drawer from "@/components/Drawer.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { dataVersion, toast } from "@/store";
import { useAction } from "@/useResource";
import { date, money, shortDate, whatsappReminder } from "@/utils";

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["close"]);

const data = ref(null);
const inv = computed(() => data.value?.invoice);
// a payment link is only offered when it is for the current balance
const link = computed(() =>
	inv.value?.payment_link_url && inv.value.payment_link_amount === inv.value.outstanding_amount
		? inv.value.payment_link_url
		: null
);
const reminder = computed(
	() => inv.value && whatsappReminder(data.value.mobile_no, inv.value, link.value)
);

const linking = useAction(() => post("get_payment_link", { name: props.name }), {
	success: "Payment link ready",
});
const makeLink = () => linking.run();
const checking = useAction(() => post("check_online_payment", { name: props.name }), {
	success: (recorded) => (recorded.length ? "Online payment recorded" : "No new payment yet"),
});
const checkPayment = () => checking.run();
const reminding = useAction(() => post("send_rent_reminder", { name: props.name }), {
	success: (statuses) =>
		statuses.includes("Sent") ? "Reminder sent" : "Reminder could not be sent, see Settings",
});
const remind = () => reminding.run();
async function copyLink() {
	try {
		await navigator.clipboard.writeText(link.value);
		toast("Link copied");
	} catch {
		toast("Couldn't copy, select the link instead", "error");
	}
}

async function load() {
	if (!props.name) return;
	try {
		data.value = await get("get_invoice", { name: props.name });
	} catch (e) {
		toast(e.message, "error");
		emit("close");
	}
}
watch(
	() => props.name,
	() => {
		data.value = null;
		load();
	},
	{ immediate: true }
);
watch(() => dataVersion.value, load);

const submitting = useAction(() => post("submit_invoice", { name: props.name }), {
	success: "Invoice submitted",
});
const deleting = useAction(() => post("delete_invoice", { name: props.name }), {
	success: "Draft deleted",
});
const submit = () => submitting.run();
async function remove() {
	await deleting.run();
	emit("close");
}
</script>
