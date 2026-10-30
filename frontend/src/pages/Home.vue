<template>
	<StaffHome v-if="boot.access" />
	<Dashboard v-else />
</template>

<script setup>
// "/" is the dashboard for managers, and what to do today for staff logins
import { defineAsyncComponent } from "vue";

import { boot } from "@/store";

const Dashboard = defineAsyncComponent(() => import("./Dashboard.vue"));
const StaffHome = defineAsyncComponent(() => import("./StaffHome.vue"));
</script>
