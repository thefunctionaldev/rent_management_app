<template>
	<div v-if="me.loaded" class="min-h-screen bg-slate-50 pb-24">
		<header class="bg-gradient-to-br from-brand-600 to-violet-600 px-5 pt-6 pb-16 text-white">
			<div class="mx-auto flex max-w-lg items-center justify-between">
				<div>
					<p class="text-sm text-white/70">{{ greeting }},</p>
					<p class="text-xl font-semibold">{{ me.first_name }}</p>
				</div>
				<div class="text-right text-sm text-white/80">
					<p class="font-medium text-white">{{ me.building?.property_name }}</p>
					<p v-if="me.landlord?.phone">
						<a :href="`tel:${me.landlord.phone}`" class="underline">Call landlord</a>
					</p>
				</div>
			</div>
		</header>

		<main class="mx-auto -mt-10 max-w-lg px-4">
			<RouterView v-slot="{ Component }">
				<component :is="Component" :key="$route.fullPath" />
			</RouterView>
		</main>

		<nav
			class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 backdrop-blur"
		>
			<div class="mx-auto grid max-w-lg grid-cols-4">
				<RouterLink
					v-for="item in nav"
					:key="item.to"
					:to="item.to"
					class="flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-slate-500"
					:class="isActive(item) && '!text-brand-600'"
				>
					<component :is="item.icon" class="size-5" :stroke-width="1.8" />
					{{ item.label }}
				</RouterLink>
			</div>
		</nav>
		<Toasts />
	</div>
	<div v-else class="grid min-h-screen place-items-center">
		<div
			class="size-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"
		/>
	</div>
</template>

<script setup>
import { Home, MessageSquareWarning, ReceiptText, UserRound } from "lucide-vue-next";
import { useRoute } from "vue-router";

import Toasts from "@/components/Toasts.vue";

import { me } from "./store";

const route = useRoute();
const nav = [
	{ to: "/", label: "Home", icon: Home },
	{ to: "/invoices", label: "Bills", icon: ReceiptText },
	{ to: "/requests", label: "Requests", icon: MessageSquareWarning },
	{ to: "/profile", label: "Profile", icon: UserRound },
];
const isActive = (item) => (item.to === "/" ? route.path === "/" : route.path.startsWith(item.to));
const hour = new Date().getHours();
const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
</script>
