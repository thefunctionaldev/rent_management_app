<template>
	<div class="flex flex-col items-center justify-center px-6 py-14 text-center">
		<span class="grid size-16 place-items-center rounded-3xl bg-brand-50 text-brand-600">
			<component :is="icon" class="size-6" />
		</span>
		<p class="mt-5 text-base font-semibold text-slate-900">{{ title }}</p>
		<p v-if="description" class="mt-2 max-w-sm text-sm leading-6 text-slate-500">
			{{ description }}
		</p>
		<div v-if="$slots.default" class="mt-5"><slot /></div>
	</div>
</template>

<script setup>
import { Inbox } from "lucide-vue-next";

defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
	icon: { type: [Object, Function], default: Inbox },
});
</script>
