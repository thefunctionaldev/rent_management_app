<template>
	<div>
		<PageHeader title="Tenants" :subtitle="`${activeCount} active · ${tenants.length} total`">
			<Button variant="primary" :icon="UserPlus" @click="openDialog('tenant')"
				>Add tenant</Button
			>
		</PageHeader>

		<div class="mb-4 flex flex-col gap-3 sm:flex-row">
			<SearchInput
				v-model="search"
				class="sm:w-80"
				placeholder="Search name, phone or email"
			/>
			<select v-model="status" class="input sm:w-40">
				<option value="">All statuses</option>
				<option>Active</option>
				<option>Inactive</option>
			</select>
		</div>

		<div class="card overflow-hidden">
			<div v-if="loading && !tenants.length" class="space-y-3 p-5">
				<Skeleton v-for="i in 6" :key="i" class="h-10" />
			</div>
			<EmptyState
				v-else-if="!tenants.length"
				:icon="Users"
				title="No tenants found"
				:description="
					search ? 'Try another search.' : 'Add a tenant to allot them a room.'
				"
			/>
			<div v-else class="overflow-x-auto">
				<table class="w-full">
					<thead class="border-b border-slate-100 bg-slate-50/60">
						<tr>
							<th class="table-head">Tenant</th>
							<th class="table-head">Phone</th>
							<th class="table-head">Room</th>
							<th class="table-head">Status</th>
							<th class="table-head text-right">Outstanding</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100">
						<tr
							v-for="t in tenants"
							:key="t.name"
							class="cursor-pointer transition hover:bg-slate-50/80"
							@click="$router.push(`/tenants/${t.name}`)"
						>
							<td class="table-cell">
								<div class="flex items-center gap-3">
									<Avatar :name="t.full_name" :image="t.display_picture" />
									<div>
										<p class="font-medium text-slate-900">{{ t.full_name }}</p>
										<p class="text-xs text-slate-500">
											{{ t.email_id || t.occupation || "—" }}
										</p>
									</div>
								</div>
							</td>
							<td class="table-cell text-slate-600">{{ t.mobile_no || "—" }}</td>
							<td class="table-cell">
								<span
									v-if="t.room"
									class="inline-flex items-center gap-1.5 rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700"
								>
									<DoorOpen class="size-3.5" />{{ t.room
									}}<template v-if="t.bed_no > 1">
										· Bed {{ t.bed_no }}</template
									>
								</span>
								<span v-else class="text-sm text-slate-400">—</span>
							</td>
							<td class="table-cell"><StatusBadge :status="t.status" /></td>
							<td
								class="table-cell tabular text-right font-medium"
								:class="t.outstanding ? 'text-amber-700' : 'text-slate-400'"
							>
								{{ t.outstanding ? money(t.outstanding) : "—" }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script setup>
import { DoorOpen, UserPlus, Users } from "lucide-vue-next";
import { computed, ref, watch } from "vue";

import { get } from "@/api";
import Avatar from "@/components/Avatar.vue";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import SearchInput from "@/components/SearchInput.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { scope } from "@/store";
import { useResource } from "@/useResource";
import { debounce, money } from "@/utils";

const search = ref("");
const status = ref("");
const { data, loading, reload } = useResource(
	() => get("get_tenants", { search: search.value, status: status.value, ...scope() }),
	{ initial: [] }
);
const tenants = computed(() => data.value || []);
const activeCount = computed(() => tenants.value.filter((t) => t.status === "Active").length);

watch(search, debounce(reload, 250));
watch(status, reload);
</script>
