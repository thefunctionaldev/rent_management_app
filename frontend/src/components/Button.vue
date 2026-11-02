<template>
	<component
		:is="href ? 'a' : 'button'"
		:href="href"
		:type="href ? undefined : type"
		:disabled="disabled || loading"
		class="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl font-medium whitespace-nowrap transition focus-visible:ring-4 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
		:class="[variants[variant], sizes[size]]"
	>
		<svg v-if="loading" class="size-4 animate-spin" viewBox="0 0 24 24" fill="none">
			<circle
				cx="12"
				cy="12"
				r="9"
				stroke="currentColor"
				stroke-opacity="0.25"
				stroke-width="3"
			/>
			<path
				d="M21 12a9 9 0 0 0-9-9"
				stroke="currentColor"
				stroke-width="3"
				stroke-linecap="round"
			/>
		</svg>
		<component :is="icon" v-else-if="icon" class="size-4" :stroke-width="2" />
		<slot />
	</component>
</template>

<script setup>
defineProps({
	variant: { type: String, default: "secondary" },
	size: { type: String, default: "md" },
	icon: { type: [Object, Function], default: null },
	loading: Boolean,
	disabled: Boolean,
	href: { type: String, default: null },
	type: { type: String, default: "button" },
});

const variants = {
	primary:
		"bg-brand-600 text-white shadow-sm shadow-brand-600/20 hover:bg-brand-700 focus-visible:ring-brand-100",
	secondary:
		"border border-slate-200 bg-white text-slate-700 shadow-xs hover:bg-slate-50 hover:text-slate-900 focus-visible:ring-slate-100",
	ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-slate-100",
	danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-700 focus-visible:ring-rose-100",
	success:
		"bg-emerald-600 text-white shadow-sm shadow-emerald-600/20 hover:bg-emerald-700 focus-visible:ring-emerald-100",
};
const sizes = {
	sm: "h-8 px-3 text-xs",
	md: "h-10 px-4 text-sm",
	lg: "h-11 px-5 text-sm",
	icon: "size-10",
};
</script>
