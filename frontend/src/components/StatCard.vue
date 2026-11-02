<template>
	<div class="card stat-card relative overflow-hidden p-5">
		<div class="flex items-start justify-between gap-3">
			<p class="text-xs font-semibold tracking-wide text-slate-500">{{ label }}</p>
			<span class="grid size-10 place-items-center rounded-xl" :class="tones[tone]">
				<component :is="icon" class="size-[18px]" :stroke-width="2" />
			</span>
		</div>
		<p class="tabular mt-3 text-3xl font-semibold tracking-tight text-slate-900">
			{{ value }}
		</p>
		<p v-if="hint" class="mt-2 text-xs leading-5 text-slate-500">{{ hint }}</p>
		<slot />
	</div>
</template>

<script setup>
defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], required: true },
	hint: { type: String, default: "" },
	icon: { type: [Object, Function], required: true },
	tone: { type: String, default: "indigo" },
});

const tones = {
	indigo: "bg-brand-50 text-brand-600",
	green: "bg-emerald-50 text-emerald-600",
	amber: "bg-amber-50 text-amber-600",
	rose: "bg-rose-50 text-rose-600",
	sky: "bg-sky-50 text-sky-600",
};
</script>
