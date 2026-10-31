<template>
	<div v-if="data" class="space-y-4">
		<a
			v-if="data.checkin_url"
			:href="data.checkin_url"
			class="card flex items-center gap-3 border-brand-200 bg-brand-50/70 p-4"
		>
			<span class="grid size-10 place-items-center rounded-full bg-brand-600 text-white"
				><PenLine class="size-5"
			/></span>
			<span class="flex-1">
				<span class="block font-medium">Finish your check-in</span>
				<span class="block text-sm text-slate-600"
					>Add your details and ID, and sign your agreement</span
				>
			</span>
			<ChevronRight class="size-5 text-slate-400" />
		</a>
		<RouterLink
			v-if="data.notice"
			to="/notices"
			class="card flex items-start gap-3 p-4 ring-2 transition hover:bg-slate-50"
			:class="data.notice.category === 'Urgent' ? 'ring-rose-200' : 'ring-brand-100'"
		>
			<span
				class="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600"
				><Megaphone class="size-5"
			/></span>
			<div class="min-w-0 flex-1">
				<p class="text-xs font-medium text-brand-700">New notice</p>
				<p class="font-medium">{{ data.notice.title }}</p>
				<p class="line-clamp-2 text-sm text-slate-500">{{ data.notice.message }}</p>
			</div>
			<ChevronRight class="mt-3 size-5 text-slate-400" />
		</RouterLink>
		<RouterLink
			v-if="data.moving_out"
			to="/moving-out"
			class="card flex items-center gap-3 p-4 ring-2 transition hover:bg-slate-50"
			:class="data.moving_out.refund_overdue ? 'ring-rose-200' : 'ring-amber-100'"
		>
			<span class="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-600"
				><DoorOpen class="size-5"
			/></span>
			<div class="flex-1">
				<p class="font-medium">{{ movingOut.title }}</p>
				<p class="text-sm text-slate-500">{{ movingOut.note }}</p>
			</div>
			<ChevronRight class="size-5 text-slate-400" />
		</RouterLink>
		<div class="card p-5">
			<template v-if="data.due > 0">
				<p class="text-sm text-slate-500">Rent due</p>
				<p class="tabular mt-1 text-3xl font-semibold tracking-tight">
					{{ money(data.due) }}
				</p>
				<p
					v-if="next"
					class="mt-1 text-sm"
					:class="overdue ? 'text-rose-600' : 'text-slate-500'"
				>
					{{ next.billing_month }} {{ next.billing_year }} ·
					{{ overdue ? "was due" : "due" }} {{ date(nextDue) }}
				</p>
				<template v-if="next && next.pay_now < next.outstanding_amount">
					<!-- less to pay now: a discount for paying early, or the next instalment -->
					<p
						v-if="next.early_discount_until"
						class="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
					>
						Pay {{ money(next.pay_now) }} by {{ date(next.early_discount_until) }} and
						save {{ money(next.outstanding_amount - next.pay_now) }}.
					</p>
					<p v-else class="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800">
						Paying in instalments: {{ money(next.pay_now) }} now, by
						{{ date(nextDue) }}.
					</p>
				</template>
				<Button
					variant="primary"
					size="lg"
					class="mt-4 w-full"
					@click="$router.push(`/invoices/${next.name}`)"
					>Pay now</Button
				>
			</template>
			<div v-else class="flex items-center gap-3">
				<span
					class="grid size-11 place-items-center rounded-full bg-emerald-50 text-emerald-600"
					><CircleCheck class="size-6"
				/></span>
				<div>
					<p class="font-semibold">You're all paid up</p>
					<p class="text-sm text-slate-500">Nothing is due right now. Thank you!</p>
				</div>
			</div>
			<p
				v-if="data.pending_confirmation"
				class="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-800"
			>
				{{ data.pending_confirmation }} payment{{
					data.pending_confirmation === 1 ? "" : "s"
				}}
				you reported {{ data.pending_confirmation === 1 ? "is" : "are" }} waiting for your
				landlord to confirm.
			</p>
		</div>

		<div v-if="data.stay" class="card p-5">
			<div class="flex items-center justify-between">
				<h2 class="font-semibold">Your stay</h2>
				<a
					href="/api/method/rent_management.portal.download_agreement"
					class="text-sm font-medium text-brand-600"
					>Agreement</a
				>
			</div>
			<dl class="mt-3 grid grid-cols-2 gap-3 text-sm">
				<div class="rounded-xl bg-slate-50 p-3">
					<dt class="text-xs text-slate-500">Room</dt>
					<dd class="font-semibold">
						{{ data.stay.room
						}}<span v-if="data.stay.bed_no" class="font-normal">
							· Bed {{ data.stay.bed_no }}</span
						>
					</dd>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<dt class="text-xs text-slate-500">Monthly rent</dt>
					<dd class="tabular font-semibold">{{ money(data.stay.rent_amount) }}</dd>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<dt class="text-xs text-slate-500">Since</dt>
					<dd class="font-semibold">{{ date(data.stay.allotment_date) }}</dd>
				</div>
				<div class="rounded-xl bg-slate-50 p-3">
					<dt class="text-xs text-slate-500">Deposit</dt>
					<dd class="tabular font-semibold">{{ money(data.stay.security_deposit) }}</dd>
				</div>
			</dl>
		</div>

		<RouterLink
			to="/requests"
			class="card flex items-center gap-3 p-4 transition hover:bg-slate-50"
		>
			<span class="grid size-10 place-items-center rounded-xl bg-amber-50 text-amber-600"
				><Wrench class="size-5"
			/></span>
			<div class="flex-1">
				<p class="font-medium">Something not working?</p>
				<p class="text-sm text-slate-500">
					{{
						data.open_requests
							? `${data.open_requests} open request${
									data.open_requests === 1 ? "" : "s"
							  }`
							: "Raise a request"
					}}
				</p>
			</div>
			<ChevronRight class="size-5 text-slate-400" />
		</RouterLink>

		<RouterLink
			v-if="me.referrals"
			to="/refer"
			class="card flex items-center gap-3 p-4 transition hover:bg-slate-50"
		>
			<span class="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-600"
				><Gift class="size-5"
			/></span>
			<div class="flex-1">
				<p class="font-medium">Refer a friend</p>
				<p class="text-sm text-slate-500">
					Get {{ money(me.referral_reward) }} off your rent when they move in
				</p>
			</div>
			<ChevronRight class="size-5 text-slate-400" />
		</RouterLink>

		<RouterLink
			to="/away"
			class="card flex items-center gap-3 p-4 transition hover:bg-slate-50"
		>
			<span class="grid size-10 place-items-center rounded-xl bg-sky-50 text-sky-600"
				><Luggage class="size-5"
			/></span>
			<div class="flex-1">
				<p class="font-medium">Going away or having a visitor?</p>
				<p class="text-sm text-slate-500">Tell the warden</p>
			</div>
			<ChevronRight class="size-5 text-slate-400" />
		</RouterLink>

		<div v-if="data.payments.length" class="card">
			<h2 class="px-5 pt-4 font-semibold">Recent payments</h2>
			<ul class="mt-2 divide-y divide-slate-100">
				<li
					v-for="p in data.payments"
					:key="p.name"
					class="flex items-center justify-between px-5 py-3 text-sm"
				>
					<div>
						<p class="font-medium">{{ p.mode_of_payment }}</p>
						<p class="text-xs text-slate-500">{{ date(p.payment_date) }}</p>
					</div>
					<p class="tabular font-semibold text-emerald-600">{{ money(p.amount) }}</p>
				</li>
			</ul>
		</div>
	</div>
	<div v-else class="space-y-4"><Skeleton class="h-40" /><Skeleton class="h-48" /></div>
</template>

<script setup>
import {
	ChevronRight,
	CircleCheck,
	DoorOpen,
	Gift,
	Luggage,
	Megaphone,
	PenLine,
	Wrench,
} from "lucide-vue-next";
import { computed } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import Skeleton from "@/components/Skeleton.vue";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

import { call, me } from "../store";

const { data } = useResource(() => get(call("get_home")));
const next = computed(() => data.value?.unpaid[0]);
const nextDue = computed(() => next.value?.next_due_date || next.value?.due_date);
const overdue = computed(() => nextDue.value && nextDue.value < me.today);

const movingOut = computed(() => {
	const m = data.value.moving_out;
	const refund = m.refund ? `${money(m.refund)} back` : "Your deposit";
	if (m.stage === "notice")
		return {
			title: `Moving out on ${date(m.moving_on)}`,
			note: m.days_left
				? `${m.days_left} day${m.days_left === 1 ? "" : "s"} to go · checklist and deposit`
				: "Today · checklist and deposit",
		};
	if (m.stage === "moved_out")
		return {
			title: m.refund_due_on ? "Your deposit refund" : "You've moved out",
			note: m.refund_due_on
				? `${refund} · ${m.refund_overdue ? "was due" : "by"} ${date(m.refund_due_on)}`
				: "See your move-out checklist",
		};
	return {
		title: "Your deposit is settled",
		note: m.refund ? `${money(m.refund)} refunded` : "See the breakdown",
	};
});
</script>
