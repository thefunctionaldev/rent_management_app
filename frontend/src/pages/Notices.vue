<template>
	<div>
		<PageHeader
			title="Notices"
			subtitle="Announcements to your tenants, in their app and on their phones"
		>
			<Button variant="primary" :icon="Plus" @click="openDialog('announcement', {})"
				>New notice</Button
			>
		</PageHeader>

		<div v-if="!data" class="space-y-4">
			<Skeleton v-for="i in 3" :key="i" class="h-28" />
		</div>
		<EmptyState
			v-else-if="!data.notices.length"
			:icon="Megaphone"
			title="No notices yet"
			description="Tell tenants about water cuts, repairs, rules or a festival dinner. They see it in the tenant app and get a notification on their phone."
		>
			<Button variant="primary" :icon="Plus" @click="openDialog('announcement', {})"
				>Write the first one</Button
			>
		</EmptyState>
		<ul v-else class="space-y-3">
			<li
				v-for="n in data.notices"
				:key="n.name"
				class="card p-5"
				:class="(n.status !== 'Published' || n.expired) && 'opacity-75'"
			>
				<div class="flex flex-wrap items-start gap-3">
					<span
						class="grid size-10 shrink-0 place-items-center rounded-xl"
						:class="tones[n.category] || tones.General"
						><component :is="icons[n.category] || Megaphone" class="size-5"
					/></span>
					<div class="min-w-0 flex-1">
						<p class="flex flex-wrap items-center gap-2 font-semibold">
							{{ n.title }}
							<Pin v-if="n.pinned" class="size-3.5 text-brand-600" />
							<span
								v-if="n.status !== 'Published'"
								class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
								>Draft</span
							>
							<span
								v-else-if="n.expired"
								class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500"
								>Ended {{ shortDate(n.expires_on) }}</span
							>
						</p>
						<p class="mt-1 line-clamp-2 text-sm whitespace-pre-line text-slate-600">
							{{ n.message }}
						</p>
						<p class="mt-2 text-xs text-slate-500">
							{{ n.property || "All buildings" }} · {{ n.category }}
							<template v-if="n.published_on">
								· published {{ shortDate(n.published_on.slice(0, 10)) }}</template
							>
							<template v-if="n.expires_on && !n.expired">
								· until {{ shortDate(n.expires_on) }}</template
							>
							<template v-if="n.messages_sent">
								· {{ n.messages_sent }} sent on WhatsApp/email</template
							>
						</p>
					</div>
					<div v-if="n.status === 'Published'" class="w-36 text-right text-sm">
						<p class="tabular font-medium">
							Seen by {{ n.seen || 0 }} of {{ n.recipients || 0 }}
						</p>
						<div class="mt-1.5 h-1.5 rounded-full bg-slate-100">
							<div
								class="h-1.5 rounded-full bg-emerald-500"
								:style="{
									width: `${
										n.recipients
											? Math.round(((n.seen || 0) / n.recipients) * 100)
											: 0
									}%`,
								}"
							/>
						</div>
					</div>
				</div>
				<div class="mt-3 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-3">
					<template v-if="n.status !== 'Published'">
						<Button size="sm" variant="ghost" :icon="Trash2" @click="remove(n)"
							>Delete</Button
						>
						<Button size="sm" @click="openDialog('announcement', { notice: n })"
							>Edit</Button
						>
						<Button size="sm" variant="primary" :icon="Megaphone" @click="publish(n)"
							>Publish</Button
						>
					</template>
					<template v-else>
						<Button size="sm" variant="ghost" :icon="Trash2" @click="remove(n)"
							>Delete</Button
						>
						<Button size="sm" @click="takeDown(n)">Take down</Button>
					</template>
				</div>
			</li>
		</ul>
	</div>
</template>

<script setup>
import {
	CalendarHeart,
	Droplets,
	Megaphone,
	Pin,
	Plus,
	ScrollText,
	Siren,
	Trash2,
	UtensilsCrossed,
	Wrench,
	Zap,
} from "lucide-vue-next";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import { openDialog } from "@/dialogs";
import { bumpData, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { shortDate } from "@/utils";

const { data } = useResource(() => get("get_notices", scope()));

const icons = {
	General: Megaphone,
	Water: Droplets,
	Electricity: Zap,
	Maintenance: Wrench,
	Food: UtensilsCrossed,
	Rules: ScrollText,
	Event: CalendarHeart,
	Urgent: Siren,
};
const tones = {
	General: "bg-brand-50 text-brand-600",
	Water: "bg-sky-50 text-sky-600",
	Electricity: "bg-amber-50 text-amber-600",
	Maintenance: "bg-slate-100 text-slate-600",
	Food: "bg-emerald-50 text-emerald-600",
	Rules: "bg-violet-50 text-violet-600",
	Event: "bg-pink-50 text-pink-600",
	Urgent: "bg-rose-50 text-rose-600",
};

async function act(method, n, message) {
	try {
		await post(method, { name: n.name });
		toast(message);
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	}
}
const publish = (n) => act("publish_notice", n, "Published to your tenants");
const takeDown = (n) => act("take_down_notice", n, "Taken off the notice board");
function remove(n) {
	if (confirm(`Delete "${n.title}"?`)) act("delete_notice", n, "Notice deleted");
}
</script>
