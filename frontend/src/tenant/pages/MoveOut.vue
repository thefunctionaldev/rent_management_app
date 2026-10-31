<template>
	<div v-if="loaded && !data" class="card p-6 text-center">
		<p class="font-semibold">Nothing to show</p>
		<p class="mt-1 text-sm text-slate-500">You have no current stay.</p>
	</div>
	<div v-else-if="data" class="space-y-4">
		<div class="card p-5">
			<RouterLink to="/profile" class="text-sm text-slate-500">← Profile</RouterLink>
			<h1 class="mt-1 text-lg font-semibold">Moving out</h1>
			<p class="text-sm text-slate-500">
				Room {{ data.room
				}}<template v-if="data.bed_no"> · Bed {{ data.bed_no }}</template> ·
				{{ data.property }}
			</p>

			<!-- giving notice -->
			<template v-if="data.stage === 'staying'">
				<p class="mt-4 text-sm">
					Give {{ data.notice_period_days }} days' notice. Your landlord is told right
					away.
				</p>
				<label class="label mt-3">Move-out date</label>
				<div class="flex gap-2">
					<input v-model="vacateDate" type="date" class="input" :min="me.today" />
					<Button variant="primary" :loading="giving" @click="giveNotice"
						>Give notice</Button
					>
				</div>
				<p
					v-if="vacateDate && vacateDate < data.earliest_date"
					class="mt-2 text-xs text-amber-700"
				>
					That's less than your {{ data.notice_period_days }} days' notice. Your landlord
					may charge rent until {{ date(data.earliest_date) }}.
				</p>
				<p
					v-if="data.lock_in_ends && vacateDate && vacateDate < data.lock_in_ends"
					class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
				>
					Your lock-in runs until {{ date(data.lock_in_ends) }}. Moving out earlier
					breaks the agreement, and the rent for the rest of the lock-in may be taken
					from your deposit.
				</p>
			</template>

			<div v-else class="mt-4 rounded-xl p-4" :class="banner.class">
				<p class="text-sm">{{ banner.label }}</p>
				<p class="text-xl font-semibold">{{ banner.title }}</p>
				<p v-if="banner.note" class="mt-1 text-sm">{{ banner.note }}</p>
			</div>
			<p
				v-if="data.stage === 'notice' && data.breaks_lock_in"
				class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
			>
				This is before your lock-in ends on {{ date(data.lock_in_ends) }}. The rent for the
				rest of the lock-in may be taken from your deposit.
			</p>
			<p v-if="data.stage === 'notice'" class="mt-3 text-xs text-slate-400">
				Changed your mind or your date? Ask your landlord to change it.
			</p>
		</div>

		<!-- where things are -->
		<div v-if="data.stage !== 'staying'" class="card p-5">
			<h2 class="font-semibold">Steps</h2>
			<ol class="mt-3 space-y-3">
				<li v-for="step in steps" :key="step.label" class="flex gap-3">
					<span
						class="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full"
						:class="
							step.done
								? 'bg-emerald-100 text-emerald-700'
								: step.late
								? 'bg-rose-100 text-rose-700'
								: 'bg-slate-100 text-slate-400'
						"
					>
						<Check v-if="step.done" class="size-4" />
						<span v-else class="size-2 rounded-full bg-current" />
					</span>
					<div>
						<p class="text-sm font-medium" :class="!step.done && 'text-slate-500'">
							{{ step.label }}
						</p>
						<p v-if="step.note" class="text-xs text-slate-500">{{ step.note }}</p>
					</div>
				</li>
			</ol>
		</div>

		<!-- the deposit -->
		<div v-if="data.deposit > 0" class="card p-5">
			<div class="flex items-center justify-between">
				<h2 class="font-semibold">Your deposit</h2>
				<span class="tabular text-sm text-slate-500">{{ money(data.deposit) }}</span>
			</div>

			<p
				v-if="!data.deposit_held"
				class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600"
			>
				Your landlord hasn't marked your deposit as collected. If you paid one, ask them
				to.
			</p>

			<template v-else-if="data.settlement">
				<dl class="tabular mt-3 space-y-2 text-sm">
					<div class="flex justify-between">
						<dt class="text-slate-500">Deposit</dt>
						<dd>{{ money(data.settlement.deposit) }}</dd>
					</div>
					<div
						v-for="(d, i) in data.settlement.deductions"
						:key="i"
						class="flex justify-between gap-3"
					>
						<dt class="text-slate-500">
							{{ d.reason
							}}<span v-if="d.description" class="block text-xs text-slate-400">{{
								d.description
							}}</span>
						</dt>
						<dd class="text-rose-600">− {{ money(d.amount) }}</dd>
					</div>
					<div v-if="data.settlement.rent_adjusted" class="flex justify-between">
						<dt class="text-slate-500">Unpaid bills paid from it</dt>
						<dd class="text-rose-600">− {{ money(data.settlement.rent_adjusted) }}</dd>
					</div>
				</dl>
				<div class="mt-3 border-t border-slate-100 pt-3">
					<template v-if="data.settlement.owes > 0">
						<p class="text-sm text-rose-600">You still owe</p>
						<p class="tabular text-2xl font-semibold text-rose-600">
							{{ money(data.settlement.owes) }}
						</p>
					</template>
					<template v-else>
						<p class="text-sm text-emerald-700">Refunded to you</p>
						<p class="tabular text-2xl font-semibold text-emerald-700">
							{{ money(data.settlement.refund) }}
						</p>
						<p v-if="data.settlement.refund > 0" class="mt-1 text-sm text-slate-500">
							{{ data.settlement.mode || "Paid" }} on {{ date(data.settlement.date)
							}}<template v-if="data.settlement.reference">
								· Ref. {{ data.settlement.reference }}</template
							>
						</p>
					</template>
					<p v-if="data.settlement.remarks" class="mt-2 text-sm text-slate-500">
						{{ data.settlement.remarks }}
					</p>
				</div>
			</template>

			<template v-else>
				<dl class="tabular mt-3 space-y-2 text-sm">
					<div class="flex justify-between">
						<dt class="text-slate-500">Deposit</dt>
						<dd>{{ money(data.deposit_held) }}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-slate-500">Unpaid bills</dt>
						<dd :class="data.estimate.unpaid && 'text-rose-600'">
							− {{ money(data.estimate.unpaid) }}
						</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-slate-500">
							Room checklist charges<span
								v-if="data.checklist.status !== 'Completed'"
								class="block text-xs text-slate-400"
								>Known once your room is checked</span
							>
						</dt>
						<dd :class="data.estimate.charges && 'text-rose-600'">
							− {{ money(data.estimate.charges) }}
						</dd>
					</div>
				</dl>
				<div class="mt-3 border-t border-slate-100 pt-3">
					<template v-if="data.estimate.owes > 0">
						<p class="text-sm text-rose-600">You'd still owe about</p>
						<p class="tabular text-2xl font-semibold text-rose-600">
							{{ money(data.estimate.owes) }}
						</p>
					</template>
					<template v-else>
						<p class="text-sm text-slate-500">You'd get back about</p>
						<p class="tabular text-2xl font-semibold">
							{{ money(data.estimate.refund) }}
						</p>
					</template>
					<p class="mt-1 text-xs text-slate-400">
						An estimate. Your last month's rent and electricity are billed when you
						move out, and are taken from this too if they're unpaid.
					</p>
				</div>
				<p
					v-if="data.refund_due_on"
					class="mt-3 rounded-lg px-3 py-2 text-sm"
					:class="
						data.refund_overdue
							? 'bg-rose-50 text-rose-800'
							: 'bg-emerald-50 text-emerald-800'
					"
				>
					<template v-if="data.refund_overdue"
						>Your refund was due by {{ date(data.refund_due_on) }}. Your landlord has
						been reminded.</template
					>
					<template v-else-if="data.refund_days"
						>Refunded within {{ data.refund_days }} days of moving out: by
						{{ date(data.refund_due_on) }}.</template
					>
					<template v-else
						>Refunded on the day you move out,
						{{ date(data.refund_due_on) }}.</template
					>
				</p>
				<p v-if="data.estimate.unpaid" class="mt-3 text-sm text-slate-500">
					Pay your
					<RouterLink to="/invoices" class="font-medium text-brand-600"
						>unpaid bills</RouterLink
					>
					to get more of it back.
				</p>
			</template>
		</div>

		<!-- where to send the refund -->
		<div v-if="data.deposit_held && !data.settlement" class="card p-5">
			<h2 class="font-semibold">Where to send your refund</h2>
			<template v-if="!editing && (data.refund_upi_id || data.refund_bank_details)">
				<dl class="mt-3 space-y-2 text-sm">
					<div v-if="data.refund_upi_id" class="flex justify-between gap-3">
						<dt class="text-slate-500">UPI ID</dt>
						<dd class="font-medium">{{ data.refund_upi_id }}</dd>
					</div>
					<div v-if="data.refund_bank_details">
						<dt class="text-slate-500">Bank account</dt>
						<dd class="mt-1 whitespace-pre-line">{{ data.refund_bank_details }}</dd>
					</div>
				</dl>
				<Button class="mt-4 w-full" @click="editing = true">Change</Button>
			</template>
			<form v-else class="mt-3 space-y-3" @submit.prevent="saveRefund">
				<div>
					<label class="label" for="upi">UPI ID</label>
					<input
						id="upi"
						v-model="refund.upi_id"
						class="input"
						placeholder="name@okbank"
						autocomplete="off"
					/>
				</div>
				<div>
					<label class="label" for="bank">Or a bank account</label>
					<textarea
						id="bank"
						v-model="refund.bank_details"
						class="input"
						rows="3"
						placeholder="Name on the account, account number, IFSC"
					/>
				</div>
				<Button variant="primary" type="submit" class="w-full" :loading="saving"
					>Save</Button
				>
			</form>
		</div>

		<!-- the room checklist -->
		<div class="card p-5">
			<h2 class="font-semibold">Room checklist</h2>
			<template v-if="data.checklist.status === 'Completed'">
				<p class="text-sm text-slate-500">
					Checked on {{ date(data.checklist.date) }}, against how it was when you moved
					in.
				</p>
				<ul class="mt-3 divide-y divide-slate-100">
					<li
						v-for="(row, i) in data.checklist.items"
						:key="i"
						class="flex items-start gap-3 py-2.5 text-sm"
					>
						<div class="min-w-0 flex-1">
							<p class="font-medium">
								{{ row.item
								}}<span v-if="row.quantity > 1" class="font-normal text-slate-500">
									× {{ row.quantity }}</span
								>
							</p>
							<p
								class="text-xs"
								:class="row.changed ? 'text-rose-600' : 'text-slate-500'"
							>
								<template v-if="row.changed"
									>{{ row.move_in_condition }} → {{ row.condition }}</template
								><template v-else>{{ row.condition }}</template
								><template v-if="row.notes"> · {{ row.notes }}</template>
							</p>
						</div>
						<span v-if="row.charge" class="tabular font-medium text-rose-600">{{
							money(row.charge)
						}}</span>
					</li>
				</ul>
				<div class="mt-2 flex justify-between border-t border-slate-100 pt-3 text-sm">
					<span class="font-medium">Charged</span>
					<span class="tabular font-semibold">{{ money(data.checklist.charges) }}</span>
				</div>
				<p v-if="data.checklist.notes" class="mt-2 text-sm text-slate-500">
					{{ data.checklist.notes }}
				</p>
			</template>
			<template v-else>
				<p class="text-sm text-slate-500">
					When you move out, the warden checks your room against how it was when you
					moved in. Damaged or missing things are charged from your deposit.
				</p>
				<ul v-if="data.move_in_items.length" class="mt-3 divide-y divide-slate-100">
					<li
						v-for="(row, i) in data.move_in_items"
						:key="i"
						class="flex justify-between py-2 text-sm"
					>
						<span
							>{{ row.item
							}}<span v-if="row.quantity > 1" class="text-slate-500">
								× {{ row.quantity }}</span
							></span
						>
						<span class="text-slate-500">{{ row.condition }} at move-in</span>
					</li>
				</ul>
			</template>
		</div>

		<!-- before leaving -->
		<div v-if="data.stage === 'notice'" class="card p-5">
			<h2 class="font-semibold">Before you leave</h2>
			<ul class="mt-3 space-y-2 text-sm text-slate-600">
				<li v-for="tip in tips" :key="tip" class="flex gap-2">
					<CircleCheck class="mt-0.5 size-4 shrink-0 text-slate-400" />{{ tip }}
				</li>
			</ul>
		</div>
	</div>
	<div v-else class="space-y-4"><Skeleton class="h-40" /><Skeleton class="h-56" /></div>
</template>

<script setup>
import { Check, CircleCheck } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Skeleton from "@/components/Skeleton.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

import { call, me } from "../store";

const loaded = ref(false); // data is null both before loading and when there's no stay
const { data, reload } = useResource(() =>
	get(call("get_move_out")).finally(() => (loaded.value = true))
);

const tips = [
	"Pay your last bills, so nothing is taken from your deposit.",
	"Leave the room clean and empty: anything left behind may be charged for clearing.",
	"Hand back every key and access card to the warden.",
	"Tell the warden when you'll leave, so they can check the room with you.",
	"Add your UPI ID or bank account above for the refund.",
];

const banner = computed(() => {
	const d = data.value;
	if (d.stage === "notice")
		return {
			label: "You move out on",
			title: date(d.moving_on),
			note:
				d.days_left > 0
					? `${d.days_left} day${d.days_left === 1 ? "" : "s"} to go`
					: "That's today",
			class: "bg-amber-50 text-amber-900",
		};
	if (d.stage === "moved_out")
		return {
			label: "You moved out on",
			title: date(d.vacate_date),
			note: d.deposit_held ? "Your deposit is being settled." : null,
			class: "bg-slate-50 text-slate-800",
		};
	return {
		label: "All done",
		title: "Your deposit is settled",
		note: `On ${date(d.settlement.date)}`,
		class: "bg-emerald-50 text-emerald-900",
	};
});

const steps = computed(() => {
	const d = data.value;
	const list = [];
	if (d.notice_given_on || d.stage === "notice")
		list.push({ label: "Notice given", done: true, note: date(d.notice_given_on) });
	list.push(
		{
			label: "Room checked",
			done: d.checklist.status === "Completed",
			note:
				d.checklist.status === "Completed"
					? `${date(d.checklist.date)} · ${money(d.checklist.charges)} charged`
					: d.stage === "notice"
					? "With the warden, on your last day"
					: "Not done yet",
		},
		{
			label: "Moved out",
			done: d.stage === "moved_out" || d.stage === "settled",
			note: d.vacate_date ? date(d.vacate_date) : d.moving_on && `On ${date(d.moving_on)}`,
		}
	);
	if (d.deposit_held)
		list.push({
			label: "Deposit settled",
			done: !!d.settlement,
			late: d.refund_overdue,
			note: d.settlement
				? date(d.settlement.date)
				: d.refund_due_on && `By ${date(d.refund_due_on)}`,
		});
	return list;
});

// giving notice
const vacateDate = ref("");
watch(
	data,
	(d) => {
		if (d && !vacateDate.value) vacateDate.value = d.earliest_date;
		if (d)
			Object.assign(refund, {
				upi_id: d.refund_upi_id || "",
				bank_details: d.refund_bank_details || "",
			});
	},
	{ immediate: true }
);
const giving = ref(false);
async function giveNotice() {
	if (!window.confirm(`Give notice to move out on ${date(vacateDate.value)}?`)) return;
	giving.value = true;
	try {
		await post(call("give_notice"), { vacate_date: vacateDate.value });
		toast("Notice sent to your landlord");
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		giving.value = false;
	}
}

// refund details
const refund = reactive({ upi_id: "", bank_details: "" });
const editing = ref(false);
const saving = ref(false);
async function saveRefund() {
	saving.value = true;
	try {
		await post(call("save_refund_details"), { ...refund });
		toast("Saved. Your landlord will refund it there.");
		editing.value = false;
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}
</script>
