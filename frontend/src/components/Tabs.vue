<template>
	<div class="segmented-control">
		<button
			v-for="tab in tabs"
			:key="tab.value"
			type="button"
			class="segmented-option inline-flex items-center gap-2 whitespace-nowrap"
			:aria-pressed="modelValue === tab.value"
			@click="$emit('update:modelValue', tab.value)"
		>
			{{ tab.label }}
			<span
				v-if="tab.count !== undefined"
				class="tabular rounded-full px-1.5 py-px text-[11px]"
				:class="
					modelValue === tab.value
						? 'bg-brand-50 text-brand-700'
						: 'bg-slate-100 text-slate-500'
				"
				>{{ tab.count }}</span
			>
		</button>
	</div>
</template>

<script setup>
defineProps({
	tabs: { type: Array, required: true },
	modelValue: { type: [String, Number], default: "" },
});
defineEmits(["update:modelValue"]);
</script>
