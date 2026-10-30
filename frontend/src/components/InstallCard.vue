<template>
	<div class="flex items-start gap-3">
		<img :src="icon" alt="" class="size-11 rounded-xl" />
		<div class="min-w-0 flex-1 text-sm">
			<p class="font-medium">{{ title }}</p>
			<p v-if="pwa.installed" class="text-slate-500">
				It's on this phone. Open it from the home screen.
			</p>
			<template v-else-if="pwa.installPrompt">
				<p class="text-slate-500">
					Opens full screen from your home screen, and works with a weak signal.
				</p>
				<Button size="sm" variant="primary" class="mt-2" :icon="Download" @click="install"
					>Install</Button
				>
			</template>
			<p v-else-if="isIOS" class="text-slate-500">
				In Safari, tap <Share class="inline size-4 align-text-bottom" /> Share, then
				<b>Add to Home Screen</b>.
			</p>
			<p v-else class="text-slate-500">
				Open this page in Chrome on your phone, then tap the menu
				<EllipsisVertical class="inline size-4 align-text-bottom" /> and
				<b>Install app</b> (or <b>Add to Home screen</b>).
			</p>
		</div>
	</div>
</template>

<script setup>
import { Download, EllipsisVertical, Share } from "lucide-vue-next";

import Button from "@/components/Button.vue";
import { install, isIOS, pwa } from "@/pwa";

defineProps({ title: { type: String, default: "Install the app" } });
const icon = "/assets/rent_management/icons/icon-192.png"; // served by Frappe, not bundled
</script>
