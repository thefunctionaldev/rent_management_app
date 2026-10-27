<template>
	<div class="space-y-4">
		<div v-if="!data" class="card space-y-3 p-5">
			<div v-for="i in 3" :key="i" class="h-16 animate-pulse rounded-xl bg-slate-100" />
		</div>
		<template v-else>
			<div class="card p-5">
				<h2 class="font-semibold">Going away?</h2>
				<p class="text-sm text-slate-500">
					Tell the warden, so nobody worries at night<template v-if="me.food">
						and your meals aren't cooked</template
					>.
					<template v-if="data.curfew">The gate closes at {{ data.curfew }}.</template>
				</p>
				<form v-if="leave" class="mt-4 space-y-3" @submit.prevent="requestLeave">
					<div class="grid grid-cols-2 gap-3">
						<Field label="Leaving on">
							<input
								v-model="leave.from_date"
								type="date"
								class="input"
								:min="me.today"
								required
							/>
						</Field>
						<Field label="Back on" hint="last night away">
							<input
								v-model="leave.to_date"
								type="date"
								class="input"
								:min="leave.from_date"
								required
							/>
						</Field>
					</div>
					<Field label="Going to">
						<input
							v-model="leave.destination"
							class="input"
							placeholder="Home, Mysuru"
						/>
					</Field>
					<Field label="Reason (optional)">
						<input v-model="leave.reason" class="input" />
					</Field>
					<div class="flex gap-2">
						<Button class="flex-1" @click="leave = null">Cancel</Button>
						<Button class="flex-1" variant="primary" type="submit" :loading="busy"
							>Ask for leave</Button
						>
					</div>
				</form>
				<Button v-else class="mt-4 w-full" :icon="Luggage" @click="leave = blankLeave()"
					>Ask for leave</Button
				>
				<ul
					v-if="data.leaves.length"
					class="mt-4 divide-y divide-slate-100 border-t border-slate-100"
				>
					<li
						v-for="l in data.leaves"
						:key="l.name"
						class="flex items-center gap-3 py-3"
					>
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">
								{{ date(l.from_date) }} – {{ date(l.to_date) }}
							</p>
							<p class="truncate text-xs text-slate-500">
								{{ [l.destination, l.decision_note].filter(Boolean).join(" · ") }}
							</p>
						</div>
						<span
							class="rounded-full px-2 py-0.5 text-xs font-medium"
							:class="tone[l.status]"
							>{{ l.status === "Requested" ? "Waiting" : l.status }}</span
						>
						<button
							v-if="
								['Requested', 'Approved'].includes(l.status) &&
								l.to_date >= me.today
							"
							class="text-xs font-medium text-slate-500 hover:text-rose-600"
							@click="cancelLeave(l)"
						>
							Cancel
						</button>
					</li>
				</ul>
			</div>

			<div class="card p-5">
				<h2 class="font-semibold">Someone visiting?</h2>
				<p class="text-sm text-slate-500">
					Let the warden know, so they're let in at the gate.
					<template v-if="data.visitors_until"
						>Visitors are allowed until {{ data.visitors_until }}.</template
					>
				</p>
				<form v-if="visitor" class="mt-4 space-y-3" @submit.prevent="expectVisitor">
					<div class="grid grid-cols-2 gap-3">
						<Field label="Name">
							<input v-model="visitor.visitor_name" class="input" required />
						</Field>
						<Field label="Phone">
							<input v-model="visitor.visitor_phone" class="input" type="tel" />
						</Field>
					</div>
					<div class="grid grid-cols-2 gap-3">
						<Field label="Coming on">
							<input
								v-model="visitor.expected_on"
								type="date"
								class="input"
								:min="me.today"
								required
							/>
						</Field>
						<Field label="Who are they?">
							<input v-model="visitor.purpose" class="input" placeholder="Parent" />
						</Field>
					</div>
					<label class="flex items-center gap-2 text-sm text-slate-700">
						<input
							v-model="visitor.overnight"
							type="checkbox"
							class="size-4 accent-brand-600"
						/>
						Staying overnight
					</label>
					<div class="flex gap-2">
						<Button class="flex-1" @click="visitor = null">Cancel</Button>
						<Button class="flex-1" variant="primary" type="submit" :loading="busy"
							>Tell the warden</Button
						>
					</div>
				</form>
				<Button
					v-else
					class="mt-4 w-full"
					:icon="UserPlus"
					@click="visitor = blankVisitor()"
					>Add a visitor</Button
				>
				<ul
					v-if="data.visitors.length"
					class="mt-4 divide-y divide-slate-100 border-t border-slate-100"
				>
					<li
						v-for="v in data.visitors"
						:key="v.name"
						class="flex items-center gap-3 py-3"
					>
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">{{ v.visitor_name }}</p>
							<p class="text-xs text-slate-500">
								{{
									v.status === "Expected"
										? `Coming ${date(v.expected_on)}`
										: visited(v)
								}}
							</p>
						</div>
						<span
							class="rounded-full px-2 py-0.5 text-xs font-medium"
							:class="tone[v.status]"
							>{{ v.status }}</span
						>
						<button
							v-if="v.status === 'Expected'"
							class="text-xs font-medium text-slate-500 hover:text-rose-600"
							@click="cancelVisitor(v)"
						>
							Cancel
						</button>
					</li>
				</ul>
			</div>
		</template>
	</div>
</template>

<script setup>
import { Luggage, UserPlus } from "lucide-vue-next";
import { ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import { toast } from "@/store";
import { date } from "@/utils";

import { call, me } from "../store";

const tone = {
	Requested: "bg-amber-50 text-amber-800",
	Approved: "bg-emerald-50 text-emerald-700",
	Rejected: "bg-rose-50 text-rose-700",
	Cancelled: "bg-slate-100 text-slate-500",
	Expected: "bg-sky-50 text-sky-700",
	Inside: "bg-emerald-50 text-emerald-700",
	Left: "bg-slate-100 text-slate-500",
};

const data = ref(null);
get(call("get_register")).then((result) => (data.value = result));

const blankLeave = () => ({ from_date: me.today, to_date: me.today, destination: "", reason: "" });
const blankVisitor = () => ({
	visitor_name: "",
	visitor_phone: "",
	expected_on: me.today,
	purpose: "",
	overnight: false,
});
const leave = ref(null);
const visitor = ref(null);

const visited = (v) =>
	v.check_in ? `Came ${date(v.check_in.slice(0, 10))}${v.overnight ? ", stayed over" : ""}` : "";

const busy = ref(false);
async function act(method, args, message) {
	busy.value = true;
	try {
		data.value = await post(call(method), args);
		toast(message);
		return true;
	} catch (e) {
		toast(e.message, "error");
		return false;
	} finally {
		busy.value = false;
	}
}
async function requestLeave() {
	if (await act("request_leave", leave.value, "Asked for leave. The warden will approve it."))
		leave.value = null;
}
async function expectVisitor() {
	const args = { ...visitor.value, overnight: visitor.value.overnight ? 1 : 0 };
	if (await act("expect_visitor", args, "The warden knows they're coming")) visitor.value = null;
}
const cancelLeave = (l) => act("cancel_leave", { name: l.name }, "Leave cancelled");
const cancelVisitor = (v) => act("cancel_visitor", { name: v.name }, "Visitor cancelled");
</script>
