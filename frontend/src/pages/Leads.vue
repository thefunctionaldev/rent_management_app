<template>
	<div>
		<PageHeader title="Leads" subtitle="Enquiries, visits and bookings until they move in">
			<Button v-if="data?.listing_enabled" :icon="Share2" :href="shareLink" target="_blank"
				>Share listing</Button
			>
			<Button variant="primary" :icon="Plus" @click="openDialog('lead', {})"
				>Add lead</Button
			>
		</PageHeader>

		<div
			v-if="data && !data.listing_enabled"
			class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-brand-900"
		>
			<span
				>Publish your listing page to get enquiries and bookings with a token, straight
				from WhatsApp and Google.</span
			>
			<RouterLink to="/settings" class="font-medium underline"
				>Turn it on in Settings</RouterLink
			>
		</div>
		<div
			v-else-if="data"
			class="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm"
		>
			<Globe class="size-4 text-slate-400" />
			<a :href="data.listing_url" target="_blank" class="font-medium text-brand-700">{{
				data.listing_url
			}}</a>
			<button class="ml-auto text-xs text-slate-500 hover:text-slate-900" @click="copy">
				Copy link
			</button>
		</div>

		<div class="mb-4 flex flex-wrap gap-1.5">
			<button
				v-for="f in filters"
				:key="f.value"
				class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition"
				:class="
					status === f.value
						? 'bg-slate-900 text-white ring-slate-900'
						: 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
				"
				@click="status = f.value"
			>
				{{ f.label }} <span class="tabular text-xs opacity-60">{{ f.count }}</span>
			</button>
		</div>

		<div v-if="status === 'referrals'" class="card">
			<p
				v-if="referrals.data"
				class="border-b border-slate-100 px-5 py-3 text-sm text-slate-600"
			>
				{{ referrals.data.moved_in }} moved in through a friend ·
				{{ money(referrals.data.rewarded) }} rewarded<template
					v-if="referrals.data.to_reward"
				>
					· {{ money(referrals.data.to_reward) }} to credit on their next rent</template
				>
				<RouterLink
					v-if="!referrals.data.enabled"
					to="/settings"
					class="ml-1 font-medium text-brand-600 hover:underline"
					>Turn on rewards in Settings</RouterLink
				>
			</p>
			<EmptyState
				v-if="referrals.data && !referrals.data.referrals.length"
				:icon="Gift"
				title="No referrals yet"
				description="Tenants share their link from the tenant app. When a friend moves in and pays, they get money off their rent."
			/>
			<ul v-else class="divide-y divide-slate-100">
				<li
					v-for="r in referrals.data?.referrals || []"
					:key="r.name"
					class="flex flex-wrap items-center gap-3 px-5 py-3"
				>
					<div class="min-w-48 flex-1">
						<p class="font-medium">
							{{ r.friend_name }}
							<span class="text-sm font-normal text-slate-500"
								>· referred by {{ r.referrer_name }}</span
							>
						</p>
						<p class="text-xs text-slate-500">
							{{ [r.property, r.friend_mobile].filter(Boolean).join(" · ") }} ·
							{{ ago(r.creation) }}
							<template v-if="r.reward_mode === 'Rent Credit'">
								· credited on {{ r.reward_invoice }}</template
							>
							<template v-else-if="r.reward_mode === 'Paid Out'">
								· paid out</template
							>
						</p>
					</div>
					<span v-if="r.reward_amount" class="tabular text-sm">{{
						money(r.reward_amount)
					}}</span>
					<StatusBadge :status="r.status" />
					<Button v-if="r.status === 'Earned'" size="sm" @click="payOut(r)"
						>Paid in cash</Button
					>
				</li>
			</ul>
		</div>

		<div v-else class="card">
			<div v-if="loading && !leads.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 4" :key="i" class="h-12" />
			</div>
			<EmptyState
				v-else-if="!leads.length"
				:icon="UserSearch"
				title="No leads here"
				description="Enquiries from your listing page show up here. Add walk-ins and phone calls too."
			/>
			<ul v-else class="divide-y divide-slate-100">
				<li
					v-for="l in leads"
					:key="l.name"
					class="flex cursor-pointer items-center gap-3 px-5 py-4 transition hover:bg-slate-50/80"
					@click="openDialog('lead', { name: l.name })"
				>
					<Avatar :name="l.lead_name" />
					<div class="min-w-0 flex-1">
						<p class="font-medium">
							{{ l.lead_name }}
							<span class="text-sm font-normal text-slate-500"
								>· {{ l.mobile_no }}</span
							>
						</p>
						<p class="truncate text-xs text-slate-500">
							{{ [l.property, l.room_type].filter(Boolean).join(" · ") }}
							<template v-if="l.move_in_date">
								· moving in {{ shortDate(l.move_in_date) }}</template
							>
							· {{ l.source
							}}<template v-if="l.referred_by_name">
								by {{ l.referred_by_name }}</template
							>
							· {{ ago(l.creation) }}
						</p>
						<p
							v-if="l.visit_on && l.status === 'Visit Scheduled'"
							class="mt-1 text-xs text-brand-700"
						>
							<CalendarClock class="inline size-3.5" /> Visit {{ when(l.visit_on) }}
						</p>
					</div>
					<span
						v-if="l.token_status"
						class="hidden rounded-full px-2 py-0.5 text-xs font-medium sm:inline"
						:class="tokenClass[l.token_status]"
						>Token {{ money(l.token_amount) }} ·
						{{
							l.token_status === "Paid" ? "paid" : l.token_status.toLowerCase()
						}}</span
					>
					<StatusBadge :status="l.status" />
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { CalendarClock, Gift, Globe, Plus, Share2, UserSearch } from "lucide-vue-next";
import { computed, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { get, post } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { boot, bumpData, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { money, shortDate } from "@/utils";

const route = useRoute();
const status = ref("open");
const { data, loading, reload } = useResource(() =>
	get("get_leads", { status: status.value === "referrals" ? "open" : status.value, ...scope() })
);
watch(status, (value) => value !== "referrals" && reload());
const referrals = reactive(useResource(() => get("get_referrals", scope())));
watch(data, (d) => d && (boot.new_leads = d.counts.New || 0)); // the sidebar badge
const leads = computed(() => data.value?.leads || []);
const counts = computed(() => data.value?.counts || {});
const filters = computed(() => [
	{ value: "open", label: "Open", count: data.value?.open || 0 },
	...["New", "Visit Scheduled", "Booked", "Moved In", "Lost"].map((s) => ({
		value: s,
		label: s,
		count: counts.value[s] || 0,
	})),
	{ value: "", label: "All", count: Object.values(counts.value).reduce((s, n) => s + n, 0) },
	...(referrals.data?.enabled || referrals.data?.referrals.length
		? [{ value: "referrals", label: "Referrals", count: referrals.data.referrals.length }]
		: []),
]);

async function payOut(r) {
	if (!confirm(`Mark ${r.referrer_name}'s ${money(r.reward_amount)} reward as paid in cash?`))
		return;
	try {
		await post("pay_out_referral", { name: r.name });
		toast("Reward paid out");
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}

const tokenClass = {
	Paid: "bg-emerald-50 text-emerald-700",
	Reported: "bg-sky-50 text-sky-700",
	Pending: "bg-amber-50 text-amber-700",
};

const shareLink = computed(
	() =>
		`https://wa.me/?text=${encodeURIComponent(
			`Rooms and beds available. See photos, prices and book: ${data.value?.listing_url}`
		)}`
);

async function copy() {
	await navigator.clipboard?.writeText(data.value.listing_url);
	toast("Link copied");
}

function when(value) {
	return new Intl.DateTimeFormat("en-IN", {
		weekday: "short",
		day: "numeric",
		month: "short",
		hour: "numeric",
		minute: "2-digit",
	}).format(new Date(value.replace(" ", "T")));
}

function ago(value) {
	const days = Math.floor((Date.now() - new Date(value.replace(" ", "T"))) / 86400000);
	return days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
}

// links from the "New lead" emails open the lead
if (route.query.lead) openDialog("lead", { name: route.query.lead });
</script>
