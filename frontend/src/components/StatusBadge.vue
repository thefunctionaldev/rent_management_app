<template>
	<span
		class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset"
		:class="color"
	>
		<span class="size-1.5 rounded-full" :class="dot" />
		{{ status }}
	</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ status: { type: String, default: "" } });

const palette = {
	green: ["bg-emerald-50 text-emerald-700 ring-emerald-600/15", "bg-emerald-500"],
	indigo: ["bg-brand-50 text-brand-700 ring-brand-600/15", "bg-brand-500"],
	amber: ["bg-amber-50 text-amber-700 ring-amber-600/20", "bg-amber-500"],
	sky: ["bg-sky-50 text-sky-700 ring-sky-600/15", "bg-sky-500"],
	rose: ["bg-rose-50 text-rose-700 ring-rose-600/15", "bg-rose-500"],
	slate: ["bg-slate-100 text-slate-600 ring-slate-500/15", "bg-slate-400"],
};

const colors = {
	Available: "green",
	Paid: "green",
	Active: "green",
	Settled: "green",
	Occupied: "indigo",
	"Partly Occupied": "sky",
	Reserved: "amber",
	Unpaid: "amber",
	"Partly Paid": "sky",
	Vacated: "slate",
	Overdue: "rose",
	Cancelled: "rose",
	Draft: "slate",
	Inactive: "slate",
	"Under Renovation": "slate",
	Trial: "sky",
	"Past Due": "amber",
	Expired: "rose",
};

const tone = computed(() => palette[colors[props.status] || "slate"]);
const color = computed(() => tone.value[0]);
const dot = computed(() => tone.value[1]);
</script>
