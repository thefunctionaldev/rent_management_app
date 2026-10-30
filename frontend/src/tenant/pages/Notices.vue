<template>
	<div class="space-y-4">
		<div class="card p-5">
			<h1 class="font-semibold">Notices</h1>
			<p class="text-sm text-slate-500">
				From the management of {{ me.building?.property_name }}.
			</p>
			<div v-if="pwa.push === 'off'" class="mt-3 border-t border-slate-100">
				<Toggle
					:model-value="false"
					:disabled="busy"
					label="Get them on this phone"
					hint="A notification when there's a new notice, even with the app closed"
					@update:model-value="turnOn"
				/>
			</div>
			<p
				v-else-if="pwa.push === 'unsupported' && isIOS && !pwa.installed"
				class="mt-3 text-xs text-slate-500"
			>
				Add the app to your home screen to get notices as notifications.
			</p>
		</div>

		<div v-if="!rows" class="card h-40 animate-pulse bg-slate-100" />
		<div v-else-if="!rows.length" class="card p-8 text-center text-sm text-slate-500">
			<Megaphone class="mx-auto mb-2 size-8 text-slate-300" />
			No notices right now.
		</div>
		<article
			v-for="n in rows"
			:key="n.name"
			class="card p-5"
			:class="n.category === 'Urgent' && 'ring-2 ring-rose-200'"
		>
			<p class="flex items-center gap-2 text-xs font-medium text-slate-500">
				<span
					class="rounded-full px-2 py-0.5"
					:class="tones[n.category] || tones.General"
					>{{ n.category }}</span
				>
				<Pin v-if="n.pinned" class="size-3.5 text-brand-600" />
				{{ shortDate(n.published_on.slice(0, 10)) }}
				<span
					v-if="n.unread"
					class="ml-auto size-2 rounded-full bg-brand-600"
					title="New"
				/>
			</p>
			<h2 class="mt-2 font-semibold">{{ n.title }}</h2>
			<p class="mt-1 text-sm whitespace-pre-line text-slate-700">{{ n.message }}</p>
			<p v-if="n.expires_on" class="mt-2 text-xs text-slate-400">
				Until {{ date(n.expires_on) }}
			</p>
		</article>
	</div>
</template>

<script setup>
import { Megaphone, Pin } from "lucide-vue-next";
import { ref } from "vue";

import { get } from "@/api";
import Toggle from "@/components/Toggle.vue";
import { enablePush, isIOS, pwa } from "@/pwa";
import { toast } from "@/store";
import { date, shortDate } from "@/utils";

import { call, me } from "../store";

const tones = {
	General: "bg-brand-50 text-brand-700",
	Water: "bg-sky-50 text-sky-700",
	Electricity: "bg-amber-50 text-amber-800",
	Maintenance: "bg-slate-100 text-slate-600",
	Food: "bg-emerald-50 text-emerald-700",
	Rules: "bg-violet-50 text-violet-700",
	Event: "bg-pink-50 text-pink-700",
	Urgent: "bg-rose-50 text-rose-700",
};

const rows = ref(null);
// opening the board marks them seen
get(call("get_notices")).then((result) => {
	rows.value = result;
	me.notices_unread = 0;
});

const busy = ref(false);
async function turnOn() {
	busy.value = true;
	try {
		await enablePush();
		toast("You'll get new notices on this phone");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = false;
	}
}
</script>
