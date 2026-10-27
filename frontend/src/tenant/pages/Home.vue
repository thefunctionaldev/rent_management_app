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
					{{ overdue ? "was due" : "due" }} {{ date(next.due_date) }}
				</p>
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
			<p
				v-if="data.stay.expected_vacate_date"
				class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
			>
				You're moving out on {{ date(data.stay.expected_vacate_date) }}.
			</p>
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
import { ChevronRight, CircleCheck, PenLine, Wrench } from "lucide-vue-next";
import { computed } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import Skeleton from "@/components/Skeleton.vue";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

import { call, me } from "../store";

const { data } = useResource(() => get(call("get_home")));
const next = computed(() => data.value?.unpaid[0]);
const overdue = computed(() => next.value?.due_date && next.value.due_date < me.today);
</script>
