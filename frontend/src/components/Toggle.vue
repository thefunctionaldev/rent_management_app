<template>
	<label class="flex cursor-pointer items-start justify-between gap-4 py-3">
		<span class="min-w-0">
			<span class="block text-sm font-medium text-slate-900">{{ label }}</span>
			<span v-if="hint" class="mt-0.5 block text-xs text-slate-500">{{ hint }}</span>
		</span>
		<span class="relative mt-0.5 shrink-0">
			<input
				type="checkbox"
				class="peer sr-only"
				:checked="!!modelValue"
				:disabled="disabled"
				@change="$emit('update:modelValue', $event.target.checked ? 1 : 0)"
			/>
			<span
				class="block h-5 w-9 rounded-full bg-slate-200 transition peer-checked:bg-brand-600 peer-focus-visible:ring-4 peer-focus-visible:ring-brand-100 peer-disabled:opacity-50"
			/>
			<span
				class="absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition peer-checked:translate-x-4"
			/>
		</span>
	</label>
</template>

<script setup>
defineProps({
	modelValue: { type: [Number, Boolean], default: 0 },
	label: { type: String, required: true },
	hint: { type: String, default: "" },
	disabled: Boolean,
});
defineEmits(["update:modelValue"]);
</script>
