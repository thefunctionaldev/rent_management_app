<template>
	<div>
		<PageHeader title="Requests" subtitle="Complaints and repairs raised by tenants">
			<Button variant="primary" :icon="Plus" @click="openDialog('request', {})"
				>New request</Button
			>
		</PageHeader>

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

		<div class="card">
			<div v-if="loading && !requests.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 4" :key="i" class="h-12" />
			</div>
			<EmptyState
				v-else-if="!requests.length"
				:icon="Wrench"
				title="No requests"
				description="Tenants raise requests from the tenant app. You can add one for them too."
			/>
			<ul v-else class="divide-y divide-slate-100">
				<li
					v-for="r in requests"
					:key="r.name"
					class="flex cursor-pointer items-start gap-3 px-5 py-4 transition hover:bg-slate-50/80"
					@click="openDialog('request', { request: r })"
				>
					<span
						class="mt-1.5 size-2 shrink-0 rounded-full"
						:class="
							{ High: 'bg-rose-500', Medium: 'bg-amber-400', Low: 'bg-slate-300' }[
								r.priority
							]
						"
						:title="`${r.priority} priority`"
					/>
					<div class="min-w-0 flex-1">
						<p class="font-medium">{{ r.subject }}</p>
						<p class="text-xs text-slate-500">
							{{ r.tenant_name }} · room {{ r.room || "—" }} · {{ r.category }} ·
							{{ shortDate(r.creation.slice(0, 10)) }}
						</p>
						<p v-if="r.description" class="mt-1 line-clamp-2 text-sm text-slate-600">
							{{ r.description }}
						</p>
					</div>
					<StatusBadge :status="r.status" />
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { Plus, Wrench } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { scope } from "@/store";
import { useResource } from "@/useResource";
import { shortDate } from "@/utils";

const status = ref("open");
const { data, loading, reload } = useResource(() =>
	get("get_requests", { status: status.value, ...scope() })
);
watch(status, reload);
const requests = computed(() => data.value?.requests || []);
const counts = computed(() => data.value?.counts || {});
const filters = computed(() => [
	{
		value: "open",
		label: "Open",
		count: (counts.value.Open || 0) + (counts.value["In Progress"] || 0),
	},
	{ value: "Resolved", label: "Resolved", count: counts.value.Resolved || 0 },
	{ value: "Closed", label: "Closed", count: counts.value.Closed || 0 },
	{ value: "", label: "All", count: Object.values(counts.value).reduce((s, n) => s + n, 0) },
]);
</script>
