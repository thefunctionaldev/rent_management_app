<template>
	<Teleport to="body">
		<Transition
			enter-active-class="duration-300 ease-out"
			enter-from-class="translate-y-full opacity-0"
			leave-active-class="duration-200 ease-in"
			leave-to-class="translate-y-full opacity-0"
		>
			<div
				v-if="show"
				class="fixed inset-x-0 bottom-0 z-50 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
				:class="iosSafari && !inAppBrowser ? 'pb-24' : ''"
				role="dialog"
				aria-label="Install the app"
			>
				<div
					class="mx-auto max-w-md rounded-2xl bg-white p-5 shadow-2xl ring-1 shadow-slate-900/20 ring-slate-200"
				>
					<div class="flex items-start gap-3">
						<img :src="icon" alt="" class="size-12 rounded-xl" />
						<div class="min-w-0 flex-1">
							<p class="font-semibold">Install {{ name }}</p>
							<p class="mt-0.5 text-sm text-slate-500">
								Open it from your home screen like any app. It's quicker, full
								screen and works with a weak signal.
							</p>
						</div>
						<button
							class="-mt-1 -mr-1 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
							title="Not now"
							@click="later"
						>
							<X class="size-5" />
						</button>
					</div>

					<!-- Android (Chrome, Edge, Samsung): the browser's own install dialog -->
					<Button
						v-if="pwa.installPrompt"
						variant="primary"
						size="lg"
						class="mt-4 w-full"
						:icon="Download"
						@click="installNow"
						>Install</Button
					>
					<p
						v-else-if="inAppBrowser"
						class="mt-4 rounded-xl bg-amber-50 px-3 py-2.5 text-sm text-amber-900"
					>
						This page is open inside another app. Tap
						<EllipsisVertical
							v-if="isAndroid"
							class="inline size-4 align-text-bottom"
						/>
						<Ellipsis v-else class="inline size-4 align-text-bottom" />
						and choose <b>Open in {{ isIOS ? "Safari" : "Chrome" }}</b
						>, then install it from there.
					</p>
					<ol
						v-else-if="isIOS"
						class="mt-4 space-y-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"
					>
						<li class="flex items-center gap-2">
							<span class="step">1</span> Tap
							<Share class="size-4 text-sky-600" />
							<b>Share</b>
							{{ iosSafari ? "below" : "at the top" }}
						</li>
						<li class="flex items-center gap-2">
							<span class="step">2</span> Choose
							<SquarePlus class="size-4" />
							<b>Add to Home Screen</b>
						</li>
						<li class="flex items-center gap-2">
							<span class="step">3</span> Tap <b>Add</b>
						</li>
					</ol>
					<ol
						v-else
						class="mt-4 space-y-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"
					>
						<li class="flex items-center gap-2">
							<span class="step">1</span> Tap the menu
							<EllipsisVertical class="size-4" />
							at the top
						</li>
						<li class="flex items-center gap-2">
							<span class="step">2</span>
							<span>Choose <b>Install app</b> or <b>Add to Home screen</b></span>
						</li>
					</ol>

					<div class="mt-3 flex justify-between text-sm">
						<button class="font-medium text-slate-500" @click="later">Not now</button>
						<button class="text-slate-400" @click="never">Don't ask again</button>
					</div>
				</div>
				<!-- Safari on iPhone: the Share button is in the bar below -->
				<ArrowDown
					v-if="iosSafari && !inAppBrowser"
					class="mx-auto mt-3 size-8 animate-bounce text-white drop-shadow-[0_1px_3px_rgba(15,23,42,0.6)]"
				/>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import {
	ArrowDown,
	Download,
	Ellipsis,
	EllipsisVertical,
	Share,
	SquarePlus,
	X,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import Button from "@/components/Button.vue";
import { inAppBrowser, install, iosSafari, isAndroid, isIOS, isPhone, pwa } from "@/pwa";

// Shown on phones every time the app is opened in the browser instead of from the home
// screen. "Not now" hides it until the next visit, "Don't ask again" on this phone for good.
defineProps({ name: { type: String, default: "the app" } });
const icon = "/assets/rent_management/icons/icon-192.png"; // served by Frappe, not bundled
const KEY = "install-prompt";

function stored(storage) {
	try {
		return storage.getItem(KEY);
	} catch {
		return null;
	}
}
function remember(storage, value) {
	try {
		storage.setItem(KEY, value);
	} catch {
		// private mode: it simply asks again
	}
}

const ready = ref(false);
const hidden = ref(stored(localStorage) === "never" || stored(sessionStorage) === "later");
const show = computed(() => ready.value && isPhone && !pwa.installed && !hidden.value);

onMounted(() => {
	// a moment, so the app shows first and Chrome can offer its install dialog
	setTimeout(() => (ready.value = true), 1500);
});

function later() {
	remember(sessionStorage, "later");
	hidden.value = true;
}
function never() {
	remember(localStorage, "never");
	hidden.value = true;
}
async function installNow() {
	if (await install()) hidden.value = true;
}
</script>

<style scoped>
.step {
	display: grid;
	place-items: center;
	width: 1.25rem;
	height: 1.25rem;
	flex-shrink: 0;
	border-radius: 9999px;
	background: white;
	font-size: 11px;
	font-weight: 600;
	color: var(--color-brand-700, #4338ca);
	box-shadow: 0 0 0 1px rgb(226 232 240);
}
</style>
