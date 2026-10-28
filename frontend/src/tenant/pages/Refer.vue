<template>
	<div class="space-y-4">
		<div v-if="!data" class="card h-64 animate-pulse bg-slate-100" />
		<template v-else>
			<div class="card overflow-hidden">
				<div class="bg-gradient-to-br from-emerald-600 to-teal-600 p-5 text-white">
					<Gift class="size-8 opacity-80" />
					<h1 class="mt-3 text-xl font-semibold">
						Get {{ money(data.reward) }} off your rent
					</h1>
					<p class="mt-1 text-sm text-white/85">
						For every friend who moves in and pays their first rent.<template
							v-if="data.friend_discount"
						>
							They get {{ money(data.friend_discount) }} off their first month
							too.</template
						>
					</p>
				</div>
				<div class="space-y-3 p-5">
					<Button
						variant="success"
						size="lg"
						class="w-full"
						:icon="MessageCircle"
						:href="`https://wa.me/?text=${encodeURIComponent(data.text)}`"
						target="_blank"
						>Share on WhatsApp</Button
					>
					<div class="flex gap-2">
						<input
							:value="data.url"
							class="input flex-1 text-sm"
							readonly
							@focus="$event.target.select()"
						/>
						<Button :icon="Copy" @click="copy">Copy</Button>
					</div>
					<Button v-if="canShare" class="w-full" :icon="Share2" @click="share"
						>More ways to share</Button
					>
					<p class="text-center text-xs text-slate-500">
						Your code: <b class="tracking-wide">{{ data.code }}</b>
					</p>
				</div>
			</div>

			<div class="card p-5">
				<div class="flex items-center justify-between">
					<h2 class="font-semibold">Your referrals</h2>
					<span v-if="data.earned" class="tabular text-sm font-medium text-emerald-700"
						>{{ money(data.earned) }} earned</span
					>
				</div>
				<p v-if="!data.referrals.length" class="mt-2 text-sm text-slate-500">
					Nobody yet. Friends who enquire through your link show up here.
				</p>
				<ul v-else class="mt-3 divide-y divide-slate-100">
					<li
						v-for="(r, i) in data.referrals"
						:key="i"
						class="flex items-center gap-3 py-2.5 text-sm"
					>
						<span class="flex-1">{{ r.friend_name }}</span>
						<span
							class="rounded-full px-2 py-0.5 text-xs font-medium"
							:class="tone[r.status]"
							>{{ labels[r.status] || r.status }}</span
						>
					</li>
				</ul>
				<p class="mt-3 text-xs text-slate-400">
					The reward comes off your next rent bill once your friend has paid their first
					rent.
				</p>
			</div>
		</template>
	</div>
</template>

<script setup>
import { Copy, Gift, MessageCircle, Share2 } from "lucide-vue-next";
import { ref } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import { toast } from "@/store";
import { money } from "@/utils";

import { call } from "../store";

const data = ref(null);
get(call("get_referral")).then((result) => (data.value = result));

const labels = {
	Enquired: "Enquired",
	"Moved In": "Moved in",
	Earned: "Reward on your next bill",
	Rewarded: "Rewarded",
	"Not Eligible": "Didn't move in",
};
const tone = {
	Enquired: "bg-sky-50 text-sky-700",
	"Moved In": "bg-brand-50 text-brand-700",
	Earned: "bg-amber-50 text-amber-800",
	Rewarded: "bg-emerald-50 text-emerald-700",
	"Not Eligible": "bg-slate-100 text-slate-500",
};

const canShare = typeof navigator !== "undefined" && !!navigator.share;
async function share() {
	try {
		await navigator.share({ text: data.value.text });
	} catch {
		// closed the share sheet
	}
}
async function copy() {
	try {
		await navigator.clipboard.writeText(data.value.url);
		toast("Link copied");
	} catch {
		toast("Couldn't copy, select the link instead", "error");
	}
}
</script>
