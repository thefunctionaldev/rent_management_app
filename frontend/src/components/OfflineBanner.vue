<template>
	<p
		v-if="!pwa.online"
		class="mb-4 flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm text-white"
	>
		<WifiOff class="size-4 shrink-0" />
		You're offline. This is what was loaded last; changes need a signal.
	</p>
</template>

<script setup>
import { WifiOff } from "lucide-vue-next";

import { pwa } from "@/pwa";
</script>
