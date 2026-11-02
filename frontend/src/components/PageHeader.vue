<template>
	<div class="page-header mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
		<div class="min-w-0">
			<slot name="eyebrow" />
			<h1 class="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900">
				{{ $t(title) }}
			</h1>
			<p v-if="subtitle" class="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
				{{ $t(subtitle) }}
			</p>
		</div>
		<div v-if="$slots.default" class="flex flex-wrap items-center gap-2">
			<slot />
		</div>
	</div>
</template>

<script setup>
defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
});
</script>
