<template>
	<div>
		<PageHeader title="Subscription & Billing" subtitle="Your plan, usage and payments" />

		<div v-if="loading && !data" class="space-y-4">
			<Skeleton class="h-40" />
			<Skeleton class="h-72" />
		</div>

		<template v-else-if="data">
			<!-- current plan -->
			<div class="card mb-6 grid gap-6 p-6 lg:grid-cols-3">
				<div class="lg:col-span-1">
					<p class="text-sm font-medium text-slate-500">Current plan</p>
					<div class="mt-2 flex items-center gap-3">
						<p class="text-2xl font-semibold tracking-tight">{{ sub.plan_title }}</p>
						<StatusBadge :status="sub.status" />
					</div>
					<p class="mt-2 text-sm text-slate-600">{{ periodText }}</p>
					<p v-if="sub.status === 'Past Due'" class="mt-2 text-sm text-amber-700">
						Renew by {{ date(sub.grace_ends_on) }} to avoid the app becoming read-only.
					</p>
					<p v-if="sub.status === 'Expired'" class="mt-2 text-sm text-rose-700">
						The app is read-only. Choose a plan below to continue.
					</p>
				</div>
				<div class="grid gap-5 sm:grid-cols-2 lg:col-span-2">
					<UsageMeter
						label="Rooms"
						:used="sub.usage.rooms"
						:limit="sub.limits.rooms"
						:icon="DoorOpen"
					/>
					<UsageMeter
						label="Manager logins"
						:used="sub.usage.users"
						:limit="sub.limits.users"
						:icon="Users"
					/>
				</div>
			</div>

			<!-- plans -->
			<div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
				<h2 class="text-lg font-semibold">Plans</h2>
				<div class="inline-flex rounded-lg bg-slate-100 p-1 text-sm">
					<button
						v-for="c in ['Monthly', 'Yearly']"
						:key="c"
						class="rounded-md px-3 py-1.5 font-medium transition"
						:class="
							cycle === c
								? 'bg-white text-slate-900 shadow-xs'
								: 'text-slate-500 hover:text-slate-800'
						"
						@click="cycle = c"
					>
						{{ c }}
						<span v-if="c === 'Yearly' && yearlySaving" class="text-emerald-600"
							>· save {{ yearlySaving }}%</span
						>
					</button>
				</div>
			</div>

			<div
				v-if="!data.online_payments"
				class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
			>
				Online payment isn't set up yet.
				<template v-if="data.support_email">
					Write to
					<a :href="`mailto:${data.support_email}`" class="font-medium underline">{{
						data.support_email
					}}</a>
					to renew.
				</template>
			</div>

			<div class="mb-8 grid gap-4 md:grid-cols-3">
				<div
					v-for="plan in data.plans"
					:key="plan.key"
					class="card flex flex-col p-6"
					:class="
						plan.key === sub.plan && sub.billing_cycle ? 'ring-2 ring-brand-500' : ''
					"
				>
					<p class="text-base font-semibold">{{ plan.title }}</p>
					<p class="mt-1 min-h-10 text-sm text-slate-500">{{ plan.description }}</p>
					<p class="mt-4">
						<span class="tabular text-3xl font-semibold tracking-tight">{{
							money(price(plan), { currency: sub.currency })
						}}</span>
						<span class="text-sm text-slate-500">
							/ {{ cycle === "Monthly" ? "month" : "year" }}</span
						>
					</p>
					<ul class="mt-5 flex-1 space-y-2 text-sm text-slate-600">
						<li v-for="f in plan.features" :key="f" class="flex gap-2">
							<Check class="mt-0.5 size-4 shrink-0 text-emerald-600" />{{ f }}
						</li>
					</ul>
					<Button
						class="mt-6 w-full"
						:variant="isCurrent(plan) ? 'secondary' : 'primary'"
						:loading="paying === plan.key"
						:disabled="!data.online_payments || !!paying || !fits(plan)"
						@click="pay(plan)"
					>
						{{ buttonLabel(plan) }}
					</Button>
					<p v-if="!fits(plan)" class="mt-2 text-center text-xs text-slate-500">
						You use more than this plan allows
					</p>
					<p
						v-else-if="switchNote(plan)"
						class="mt-2 text-center text-xs text-slate-500"
					>
						{{ switchNote(plan) }}
					</p>
				</div>
			</div>

			<!-- history -->
			<div class="card">
				<div class="border-b border-slate-100 px-5 py-4">
					<h2 class="font-semibold">Payment history</h2>
				</div>
				<EmptyState v-if="!data.payments.length" :icon="Receipt" title="No payments yet" />
				<div v-else class="overflow-x-auto">
					<table class="w-full">
						<thead class="border-b border-slate-100 bg-slate-50/60">
							<tr>
								<th class="table-head">Paid on</th>
								<th class="table-head">Plan</th>
								<th class="table-head">Period</th>
								<th class="table-head">Reference</th>
								<th class="table-head text-right">Amount</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100">
							<tr v-for="p in data.payments" :key="p.name">
								<td class="table-cell text-slate-600">
									{{ date(p.paid_on?.slice(0, 10)) }}
								</td>
								<td class="table-cell">
									<p class="font-medium">{{ p.plan_title }}</p>
									<p class="text-xs text-slate-500">{{ p.billing_cycle }}</p>
								</td>
								<td class="table-cell text-slate-600">
									{{ date(p.period_start) }} – {{ date(p.period_end) }}
									<p v-if="p.bonus_days" class="text-xs text-emerald-600">
										+{{ p.bonus_days }} days carried over
									</p>
								</td>
								<td class="table-cell text-slate-500">
									{{ p.razorpay_payment_id || p.payment_method }}
								</td>
								<td class="table-cell tabular text-right font-semibold">
									{{ money(p.amount, { currency: p.currency }) }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { Check, DoorOpen, Receipt, Users } from "lucide-vue-next";
import { computed, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import UsageMeter from "@/components/UsageMeter.vue";
import { boot, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

const { data, loading, reload } = useResource(() => get("get_billing"));
const sub = computed(() => data.value.subscription);
const cycle = ref(boot.subscription?.billing_cycle || "Monthly");
const paying = ref(null);

const price = (plan) => (cycle.value === "Monthly" ? plan.monthly : plan.yearly);
// billing_cycle is only set once a plan has been paid for
const isCurrent = (plan) => plan.key === sub.value.plan && cycle.value === sub.value.billing_cycle;
const fits = (plan) =>
	(!plan.max_rooms || sub.value.usage.rooms <= plan.max_rooms) &&
	(!plan.max_users || sub.value.usage.users <= plan.max_users);
const running = computed(() => sub.value.status === "Active");

function buttonLabel(plan) {
	if (isCurrent(plan)) return "Renew";
	if (sub.value.status === "Trial" || !running.value) return `Choose ${plan.title}`;
	return `Switch to ${plan.title}`;
}

function switchNote(plan) {
	if (isCurrent(plan) && running.value)
		return `Adds a ${cycle.value === "Monthly" ? "month" : "year"} after ${date(
			sub.value.current_period_end
		)}`;
	if (running.value) return "Starts today; unused days of your plan carry over";
	return "";
}

const yearlySaving = computed(() => {
	const plan = data.value?.plans?.[0];
	if (!plan?.monthly || !plan?.yearly) return 0;
	return Math.round((1 - plan.yearly / (plan.monthly * 12)) * 100);
});

const periodText = computed(() => {
	const s = sub.value;
	if (s.status === "Trial")
		return `Free trial ends ${date(s.trial_ends_on)} (${s.days_left} day${
			s.days_left === 1 ? "" : "s"
		} left)`;
	if (s.status === "Active")
		return `Billed ${s.billing_cycle?.toLowerCase()}, paid until ${date(
			s.current_period_end
		)}`;
	if (s.status === "Past Due") return `Ended on ${date(s.current_period_end)}`;
	return s.ends_on ? `Ended on ${date(s.ends_on)}` : "No active plan";
});

let checkoutScript;
function loadCheckout() {
	checkoutScript ??= new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = "https://checkout.razorpay.com/v1/checkout.js";
		script.onload = resolve;
		script.onerror = () => {
			checkoutScript = null;
			reject(new Error("Could not load the payment window. Check your connection."));
		};
		document.head.appendChild(script);
	});
	return checkoutScript;
}

async function pay(plan) {
	paying.value = plan.key;
	try {
		await loadCheckout();
		const options = await post("create_subscription_checkout", {
			plan: plan.key,
			billing_cycle: cycle.value,
		});
		delete options.payment; // ours, not a Razorpay option
		await new Promise((resolve) => {
			const checkout = new window.Razorpay({
				...options,
				theme: { color: "#4f46e5" },
				modal: { ondismiss: resolve },
				handler: async (response) => {
					try {
						const state = await post("verify_subscription_payment", response);
						boot.subscription = state;
						toast(
							`Thank you! ${plan.title} is active until ${date(
								state.current_period_end
							)}.`
						);
						reload();
					} catch (e) {
						toast(e.message, "error");
					}
					resolve();
				},
			});
			checkout.on("payment.failed", (response) => {
				toast(response.error?.description || "Payment failed", "error");
			});
			checkout.open();
		});
	} catch (e) {
		toast(e.message, "error");
	} finally {
		paying.value = null;
	}
}
</script>
