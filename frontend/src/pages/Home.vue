<template>
	<StaffHome v-if="boot.access" />
	<div v-else>
		<RouterLink
			v-if="setup && setup.steps.some((s) => !s.done)"
			to="/setup"
			class="card mb-6 flex items-center justify-between gap-3 p-5 text-sm"
		>
			<span
				><strong>Finish setting up your property</strong
				><span class="mt-1 block text-slate-500"
					>{{ setup.steps.filter((s) => s.done).length }} of 5 steps complete. Pick up
					where you left off.</span
				></span
			><span class="font-semibold text-brand-600">Continue →</span>
		</RouterLink>
		<Dashboard />
	</div>
</template>

<script setup>
// "/" is the dashboard for managers, and what to do today for staff logins
import { defineAsyncComponent } from "vue";

import { get } from "@/api";
import { useResource } from "@/useResource";
import { boot } from "@/store";

const { data: setup } = useResource(
	() => (boot.access ? Promise.resolve(null) : get("get_setup_progress")),
	{ immediate: !boot.access }
);
const Dashboard = defineAsyncComponent(() => import("./Dashboard.vue"));
const StaffHome = defineAsyncComponent(() => import("./StaffHome.vue"));
</script>
