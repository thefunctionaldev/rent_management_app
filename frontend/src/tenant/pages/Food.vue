<template>
	<div class="space-y-4">
		<div v-if="!data" class="card space-y-3 p-5">
			<div v-for="i in 3" :key="i" class="h-16 animate-pulse rounded-xl bg-slate-100" />
		</div>
		<template v-else>
			<div class="card p-5">
				<h2 class="font-semibold">Your meals</h2>
				<p class="text-sm text-slate-500">
					Not eating? Skip a meal up to {{ data.cutoff_hours }} hours before, so less
					food is wasted.
				</p>
			</div>
			<div v-for="d in data.days" :key="d.date" class="card">
				<p class="border-b border-slate-100 px-5 py-3 text-sm font-semibold">
					{{ label(d) }}
				</p>
				<ul class="divide-y divide-slate-100">
					<li
						v-for="m in d.meals"
						:key="m.meal"
						class="flex items-center gap-3 px-5 py-3"
					>
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">
								{{ m.meal }}
								<span class="font-normal text-slate-400">· {{ m.time }}</span>
							</p>
							<p class="truncate text-xs text-slate-500">
								{{ m.dishes || "Menu not set" }}
							</p>
						</div>
						<button
							class="rounded-full px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50"
							:class="
								m.eating
									? 'bg-emerald-50 text-emerald-700'
									: 'bg-slate-100 text-slate-500 line-through'
							"
							:disabled="!m.can_change || busy === key(d, m)"
							@click="toggle(d, m)"
						>
							{{ m.eating ? "Eating" : "Skipped" }}
						</button>
					</li>
				</ul>
			</div>
			<p class="text-center text-xs text-slate-400">
				Tap to skip or eat again. Greyed out: too late to change.
			</p>
		</template>
	</div>
</template>

<script setup>
import { ref } from "vue";

import { get, post } from "@/api";
import { toast } from "@/store";

import { call } from "../store";

const data = ref(null);
get(call("get_food")).then((result) => (data.value = result));

const key = (d, m) => `${d.date}-${m.meal}`;
const busy = ref(null);
async function toggle(d, m) {
	busy.value = key(d, m);
	try {
		data.value = await post(call("skip_meal"), {
			date: d.date,
			meal: m.meal,
			skip: m.eating ? 1 : 0,
		});
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = null;
	}
}

function label(d) {
	const date = new Date(`${d.date}T00:00:00`);
	const today = new Date();
	const tomorrow = new Date();
	tomorrow.setDate(today.getDate() + 1);
	if (date.toDateString() === today.toDateString()) return "Today";
	if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";
	return date.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
}
</script>
