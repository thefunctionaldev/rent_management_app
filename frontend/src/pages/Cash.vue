<template>
	<div>
		<PageHeader
			title="Cash book"
			:subtitle="
				data?.manager
					? 'Who is holding how much cash, and where it went'
					: 'The cash you have collected, spent and handed over'
			"
		>
			<Button
				v-if="data && available > 0"
				variant="primary"
				:icon="HandCoins"
				@click="
					handover = {
						to_user: data.receivers[0]?.name || '',
						amount: available,
						note: '',
					}
				"
				>Hand over cash</Button
			>
		</PageHeader>

		<div v-if="!data" class="space-y-4">
			<Skeleton class="h-28" />
			<Skeleton class="h-72" />
		</div>
		<template v-else>
			<div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
				<StatCard
					label="You hold"
					:value="money(data.me.balance)"
					:hint="
						data.me.balance < 0
							? `You paid out ${money(-data.me.balance)} more than you collected`
							: data.me.pending
							? `${money(data.me.pending)} handed over, waiting to be confirmed`
							: 'In cash'
					"
					:icon="Wallet"
					tone="green"
				/>
				<StatCard
					v-if="data.manager"
					label="Cash with everyone"
					:value="money(data.total)"
					:hint="`${data.holders.length} ${
						data.holders.length === 1 ? 'person' : 'people'
					}`"
					:icon="Users"
				/>
			</div>

			<!-- handed to you -->
			<div v-if="data.to_confirm.length" class="card mb-6 ring-2 ring-amber-200">
				<h3 class="border-b border-slate-100 px-5 py-4 font-semibold">Handed to you</h3>
				<ul class="divide-y divide-slate-100">
					<li
						v-for="h in data.to_confirm"
						:key="h.name"
						class="flex flex-wrap items-center gap-3 px-5 py-3"
					>
						<div class="min-w-0 flex-1">
							<p class="font-medium">
								{{ h.from_name || h.from_user }} · {{ money(h.amount) }}
							</p>
							<p class="text-xs text-slate-500">
								{{ date(h.handed_on)
								}}<template v-if="h.note"> · {{ h.note }}</template>
							</p>
						</div>
						<Button size="sm" @click="confirm(h, 0)">Didn't get it</Button>
						<Button size="sm" variant="primary" @click="confirm(h, 1)"
							>I have it</Button
						>
					</li>
				</ul>
			</div>

			<!-- your handovers waiting -->
			<div v-if="data.my_pending.length" class="card mb-6">
				<h3 class="border-b border-slate-100 px-5 py-4 font-semibold">
					Waiting to be confirmed
				</h3>
				<ul class="divide-y divide-slate-100">
					<li
						v-for="h in data.my_pending"
						:key="h.name"
						class="flex items-center gap-3 px-5 py-3 text-sm"
					>
						<span class="flex-1"
							>{{ money(h.amount) }} to {{ h.to_name || h.to_user }} on
							{{ shortDate(h.handed_on) }}</span
						>
						<button
							class="text-xs font-medium text-slate-500 hover:text-rose-600"
							@click="cancel(h)"
						>
							Cancel
						</button>
					</li>
				</ul>
			</div>

			<!-- who holds it (managers) -->
			<div v-if="data.manager && data.holders.length" class="card mb-6 overflow-x-auto">
				<table class="w-full min-w-[40rem] text-sm">
					<thead class="bg-slate-50/60">
						<tr>
							<th class="table-head">Who</th>
							<th class="table-head text-right">Collected</th>
							<th class="table-head text-right">Spent</th>
							<th class="table-head text-right">Received</th>
							<th class="table-head text-right">Handed over</th>
							<th class="table-head text-right">Holds now</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr v-for="h in data.holders" :key="h.user">
							<td class="table-cell">
								<p class="font-medium">{{ h.full_name }}</p>
								<p v-if="h.balance < 0" class="text-xs text-amber-700">
									Paid {{ money(-h.balance) }} from their own pocket: owed to
									them
								</p>
								<p v-if="h.pending" class="text-xs text-amber-700">
									{{ money(h.pending) }} handed over, not confirmed
								</p>
							</td>
							<td class="table-cell tabular text-right">{{ money(h.collected) }}</td>
							<td class="table-cell tabular text-right">{{ money(h.spent) }}</td>
							<td class="table-cell tabular text-right">{{ money(h.received) }}</td>
							<td class="table-cell tabular text-right">
								{{ money(h.handed_over) }}
							</td>
							<td class="table-cell tabular text-right font-semibold">
								{{ money(h.balance) }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- the book -->
			<div class="card">
				<div
					class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4"
				>
					<h3 class="font-semibold">Day by day</h3>
					<div class="flex items-center gap-2 text-sm">
						<input
							v-model="range.from"
							type="date"
							class="input w-40 py-1.5"
							:max="range.to"
						/>
						<span class="text-slate-400">to</span>
						<input
							v-model="range.to"
							type="date"
							class="input w-40 py-1.5"
							:max="boot.today"
						/>
					</div>
				</div>
				<p v-if="!days.length" class="px-5 py-8 text-center text-sm text-slate-500">
					No cash in or out in these days.
				</p>
				<div v-for="d in days" :key="d.date">
					<div
						class="flex justify-between bg-slate-50/70 px-5 py-2 text-xs font-medium text-slate-500"
					>
						<span>{{ date(d.date) }}</span>
						<span class="tabular"
							><span class="text-emerald-700">+{{ money(d.in) }}</span> ·
							<span class="text-rose-700">−{{ money(d.out) }}</span></span
						>
					</div>
					<ul class="divide-y divide-slate-100">
						<li
							v-for="(e, i) in d.rows"
							:key="i"
							class="flex items-center gap-3 px-5 py-2.5 text-sm"
						>
							<span
								class="w-24 shrink-0 rounded-full px-2 py-0.5 text-center text-xs font-medium"
								:class="tones[e.kind]"
								>{{ e.kind }}</span
							>
							<div class="min-w-0 flex-1">
								<p class="truncate">{{ e.description }}</p>
								<p v-if="data.manager" class="text-xs text-slate-500">
									{{ names[e.user] || e.user
									}}<template v-if="e.property"> · {{ e.property }}</template>
								</p>
							</div>
							<span
								class="tabular font-medium"
								:class="e.amount < 0 ? 'text-rose-700' : 'text-emerald-700'"
								>{{ e.amount < 0 ? "−" : "+"
								}}{{ money(Math.abs(e.amount)) }}</span
							>
						</li>
					</ul>
				</div>
			</div>
		</template>

		<Modal
			:open="!!handover"
			title="Hand over cash"
			subtitle="They confirm when they have it"
			@close="handover = null"
		>
			<form v-if="handover" id="handover-form" class="space-y-4" @submit.prevent="handOver">
				<Field label="To">
					<select v-model="handover.to_user" class="input" required>
						<option v-for="r in data.receivers" :key="r.name" :value="r.name">
							{{ r.full_name }}
						</option>
					</select>
				</Field>
				<Field label="Amount" :hint="`You can hand over up to ${money(available)}`">
					<input
						v-model.number="handover.amount"
						type="number"
						min="1"
						:max="available"
						class="input tabular"
						required
					/>
				</Field>
				<Field label="Note">
					<input
						v-model="handover.note"
						class="input"
						placeholder="October rent, room 101 to 104"
					/>
				</Field>
			</form>
			<template #footer>
				<Button @click="handover = null">Cancel</Button>
				<Button variant="primary" type="submit" form="handover-form" :loading="busy"
					>Hand over</Button
				>
			</template>
		</Modal>
	</div>
</template>

<script setup>
import { HandCoins, Users, Wallet } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { boot, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money, shortDate } from "@/utils";

const monthStart = `${boot.today.slice(0, 8)}01`;
const range = reactive({ from: monthStart, to: boot.today });
const { data, reload } = useResource(() =>
	get("get_cash_book", { from_date: range.from, to_date: range.to, ...scope() })
);
watch(range, reload);

const tones = {
	Collected: "bg-emerald-50 text-emerald-700",
	Received: "bg-sky-50 text-sky-700",
	Spent: "bg-amber-50 text-amber-800",
	"Handed over": "bg-slate-100 text-slate-600",
};
const available = computed(() =>
	data.value
		? Math.max(Math.round((data.value.me.balance - data.value.me.pending) * 100) / 100, 0)
		: 0
);
const names = computed(() =>
	Object.fromEntries(
		[...(data.value?.holders || []), ...(data.value?.receivers || [])].map((h) => [
			h.user || h.name,
			h.full_name,
		])
	)
);
const days = computed(() => {
	const byDay = new Map();
	for (const e of data.value?.entries || []) {
		const day = byDay.get(e.date) || { date: e.date, in: 0, out: 0, rows: [] };
		day.rows.push(e);
		if (e.amount >= 0) day.in += e.amount;
		else day.out -= e.amount;
		byDay.set(e.date, day);
	}
	return [...byDay.values()];
});

const handover = ref(null);
const busy = ref(false);
async function handOver() {
	busy.value = true;
	try {
		await post("hand_over_cash", handover.value);
		toast("Handed over. They'll confirm when they have it");
		handover.value = null;
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = false;
	}
}
async function confirm(h, accept) {
	try {
		await post("confirm_cash_handover", { name: h.name, accept });
		toast(accept ? `${money(h.amount)} is with you now` : "Marked as not received");
		reload();
	} catch (e) {
		toast(e.message, "error");
	}
}
async function cancel(h) {
	try {
		await post("cancel_cash_handover", { name: h.name });
		toast("Handover cancelled");
		reload();
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
