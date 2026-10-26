<template>
	<div class="rounded-xl bg-slate-50 p-4">
		<div class="flex items-center justify-between text-sm">
			<span class="inline-flex items-center gap-2 font-medium text-slate-600">
				<component :is="icon" class="size-4" :stroke-width="2" />{{ label }}
			</span>
			<span class="tabular font-semibold text-slate-900"
				>{{ used
				}}<span class="font-normal text-slate-500">
					/ {{ limit || "Unlimited" }}</span
				></span
			>
		</div>
		<div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
			<div
				class="h-full rounded-full transition-all"
				:class="
					percent >= 100
						? 'bg-rose-500'
						: percent >= 80
						? 'bg-amber-500'
						: 'bg-brand-500'
				"
				:style="{ width: `${limit ? Math.min(percent, 100) : 4}%` }"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	label: { type: String, required: true },
	used: { type: Number, default: 0 },
	limit: { type: Number, default: 0 },
	icon: { type: [Object, Function], required: true },
});

const percent = computed(() => (props.limit ? (props.used / props.limit) * 100 : 0));
</script>
