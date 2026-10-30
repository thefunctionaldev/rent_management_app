<template>
	<section id="this-phone" class="card space-y-4 p-5">
		<h2 class="font-semibold">This phone</h2>
		<InstallCard />
		<div class="border-t border-slate-100 pt-4">
			<Toggle
				:model-value="pwa.push === 'on'"
				:disabled="busy || pwa.push === 'unsupported' || pwa.push === 'blocked'"
				label="Notifications on this phone"
				:hint="hint"
				@update:model-value="toggle"
			/>
			<button
				v-if="pwa.push === 'on'"
				class="text-xs font-medium text-brand-600 hover:underline"
				@click="test"
			>
				Send a test notification
			</button>
		</div>
	</section>
</template>

<script setup>
import { computed, ref } from "vue";

import { post } from "@/api";
import InstallCard from "@/components/InstallCard.vue";
import Toggle from "@/components/Toggle.vue";
import { disablePush, enablePush, isIOS, pwa } from "@/pwa";
import { toast } from "@/store";

const props = defineProps({
	what: { type: String, default: "New leads, leave requests and payments to confirm" },
});

const busy = ref(false);
const hint = computed(
	() =>
		({
			on: props.what,
			off: `${props.what}, even when the app is closed`,
			blocked: "Blocked for this site. Allow notifications in the browser's site settings.",
			unsupported: isIOS
				? "On iPhone, add the app to your home screen first, then turn them on from there"
				: "This browser can't show notifications",
		}[pwa.push] || "")
);
async function toggle(on) {
	busy.value = true;
	try {
		await (on ? enablePush() : disablePush());
		toast(on ? "Notifications are on for this phone" : "Notifications are off for this phone");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		busy.value = false;
	}
}
async function test() {
	try {
		await post("rent_management.pwa.test_push");
		toast("Sent. It should show on this phone in a few seconds");
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
