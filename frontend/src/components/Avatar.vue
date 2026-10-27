<template>
	<img
		v-if="image"
		:src="image"
		:alt="name"
		class="shrink-0 rounded-full object-cover"
		:class="sizes[size]"
	/>
	<span
		v-else
		class="grid shrink-0 place-items-center rounded-full font-semibold"
		:class="[sizes[size], tone]"
		>{{ initials(name) }}</span
	>
</template>

<script setup>
import { computed } from "vue";

import { initials } from "@/utils";

const props = defineProps({
	name: { type: String, default: "" },
	image: { type: String, default: null },
	size: { type: String, default: "md" },
});

const sizes = {
	sm: "size-7 text-[11px]",
	md: "size-9 text-xs",
	lg: "size-14 text-lg",
	xl: "size-16 text-xl",
};
const tones = [
	"bg-brand-100 text-brand-700",
	"bg-emerald-100 text-emerald-700",
	"bg-amber-100 text-amber-700",
	"bg-sky-100 text-sky-700",
	"bg-rose-100 text-rose-700",
	"bg-violet-100 text-violet-700",
];
const tone = computed(() => {
	const sum = [...(props.name || "")].reduce((total, ch) => total + ch.charCodeAt(0), 0);
	return tones[sum % tones.length];
});
</script>
