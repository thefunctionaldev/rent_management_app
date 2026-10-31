<template>
	<button
		type="button"
		:class="compact ? 'rounded-lg p-2 text-slate-600 hover:bg-slate-100' : buttonClass"
		aria-label="Search tenants"
		@click="show"
	>
		<Search class="size-4" :class="!compact && 'text-slate-400'" />
		<template v-if="!compact">
			<span class="flex-1 text-left">Search tenants</span>
			<kbd class="rounded border border-slate-200 px-1.5 text-[11px] text-slate-400">/</kbd>
		</template>
	</button>

	<Teleport to="body">
		<div
			v-if="open"
			class="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/30 px-4 pt-[12vh]"
			@click.self="hide"
		>
			<div class="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl">
				<div class="flex items-center gap-3 border-b border-slate-100 px-4">
					<Search class="size-5 text-slate-400" />
					<input
						ref="input"
						v-model="text"
						class="h-14 flex-1 bg-transparent text-base outline-none"
						placeholder="Name, phone, room number or UTR"
						@keydown.down.prevent="move(1)"
						@keydown.up.prevent="move(-1)"
						@keydown.enter.prevent="go(results[active])"
						@keydown.esc="hide"
					/>
					<Loader2 v-if="loading" class="size-4 animate-spin text-slate-400" />
				</div>
				<ul v-if="results.length" class="max-h-[50vh] overflow-y-auto py-2">
					<li v-for="(r, i) in results" :key="r.name">
						<button
							type="button"
							class="flex w-full items-center gap-3 px-4 py-2.5 text-left"
							:class="i === active ? 'bg-brand-50' : 'hover:bg-slate-50'"
							@mouseenter="active = i"
							@click="go(r)"
						>
							<Avatar :name="r.full_name" :image="r.picture" size="sm" />
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-medium">{{ r.full_name }}</p>
								<p class="truncate text-xs text-slate-500">
									<template v-if="r.room"
										>Room {{ r.room
										}}<template v-if="r.bed_no">
											· bed {{ r.bed_no }}</template
										>
										· {{ r.property }}</template
									>
									<template v-else>Not staying now</template>
									<template v-if="r.mobile_no"> · {{ r.mobile_no }}</template>
								</p>
							</div>
							<span
								v-if="r.match !== 'name'"
								class="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500"
								>{{ labels[r.match] }}</span
							>
						</button>
					</li>
				</ul>
				<p
					v-else-if="text.trim() && !loading && searched"
					class="px-4 py-6 text-center text-sm text-slate-500"
				>
					No tenant found for "{{ text.trim() }}".
				</p>
				<p v-else-if="!text.trim()" class="px-4 py-5 text-sm text-slate-400">
					Try a name, a phone number like 98450 12345, a room like 201, or a payment's
					UTR.
				</p>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { Loader2, Search } from "lucide-vue-next";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import { scope } from "@/store";
import { debounce } from "@/utils";

defineProps({ compact: { type: Boolean, default: false } });

const buttonClass =
	"flex w-full items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500 transition hover:border-slate-300 hover:bg-slate-50";
const labels = { phone: "Phone", room: "Room", payment: "Payment UTR", email: "Email" };

const router = useRouter();
const open = ref(false);
const text = ref("");
const results = ref([]);
const active = ref(0);
const loading = ref(false);
const searched = ref(false);
const input = ref(null);

async function show() {
	open.value = true;
	await nextTick();
	input.value?.focus();
}
function hide() {
	open.value = false;
	text.value = "";
	results.value = [];
	searched.value = false;
}
function move(step) {
	if (results.value.length)
		active.value = (active.value + step + results.value.length) % results.value.length;
}
function go(row) {
	if (!row) return;
	hide();
	router.push(`/tenants/${row.name}`);
}

let asked = 0;
const lookUp = debounce(async () => {
	const query = text.value.trim();
	if (!query) return (results.value = []);
	const ticket = ++asked;
	loading.value = true;
	try {
		const rows = await get("quick_search", { text: query, ...scope() });
		if (ticket !== asked) return; // an older answer arriving late
		results.value = rows;
		active.value = 0;
		searched.value = true;
	} finally {
		if (ticket === asked) loading.value = false;
	}
}, 200);
watch(text, lookUp);

// "/" anywhere (but not while typing) opens it
function onKey(event) {
	const typing =
		["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName) ||
		event.target.isContentEditable;
	if (event.key === "/" && !typing && !open.value) {
		event.preventDefault();
		show();
	}
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>
