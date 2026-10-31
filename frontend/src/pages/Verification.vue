<template>
	<div>
		<PageHeader
			title="Police verification"
			subtitle="Every tenant's verification form, submitted to the police and cleared"
		/>

		<div
			v-if="data && !data.enabled"
			class="card mb-6 flex flex-wrap items-center justify-between gap-3 p-5"
		>
			<p class="text-sm text-slate-600">
				Turn on tracking and every new tenant starts as "to submit", with a reminder when
				it's due.
			</p>
			<Button variant="primary" :loading="enabling" @click="enable"
				>Track police verification</Button
			>
		</div>

		<div v-if="!data" class="space-y-4">
			<Skeleton class="h-24" />
			<Skeleton class="h-48" />
		</div>
		<template v-else>
			<div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<StatCard
					label="Overdue"
					:value="data.overdue.length"
					:hint="`Not submitted ${data.due_days} days after moving in`"
					:icon="AlarmClock"
					tone="rose"
				/>
				<StatCard
					label="To submit"
					:value="data.pending.length"
					hint="Still within the days"
					:icon="FileText"
					tone="amber"
				/>
				<StatCard
					label="With the police"
					:value="data.submitted.length"
					hint="Submitted, not cleared yet"
					:icon="Clock"
					tone="sky"
				/>
				<StatCard
					label="Verified"
					:value="data.done.filter((d) => d.police_verification === 'Verified').length"
					hint="Recently"
					:icon="ShieldCheck"
					tone="green"
				/>
			</div>

			<p v-if="data.untracked" class="mb-4 text-sm text-slate-500">
				{{ data.untracked }} current
				{{ data.untracked === 1 ? "tenant" : "tenants" }} moved in before tracking started:
				open their profile to track theirs too.
			</p>

			<section v-for="group in groups" :key="group.key" class="mb-6">
				<template v-if="data[group.key].length">
					<h3 class="mb-2 text-sm font-semibold text-slate-700">{{ group.label }}</h3>
					<ul class="card divide-y divide-slate-100">
						<li
							v-for="s in data[group.key]"
							:key="s.name"
							class="flex flex-wrap items-center gap-3 px-5 py-3"
						>
							<div class="min-w-48 flex-1">
								<RouterLink
									:to="`/tenants/${s.tenant}`"
									class="font-medium hover:underline"
									>{{ s.tenant_name }}</RouterLink
								>
								<p class="text-xs text-slate-500">
									Room {{ s.room }} · {{ s.property }} · moved in
									{{ shortDate(s.allotment_date) }}
									<template v-if="group.key === 'overdue'">
										·
										<b class="text-rose-600"
											>{{ s.days_overdue }} days overdue</b
										></template
									>
									<template v-else-if="group.key === 'pending'">
										· due {{ shortDate(s.due_on) }}</template
									>
									<template v-else-if="group.key === 'submitted'">
										· submitted {{ shortDate(s.verification_submitted_on) }}
										<template v-if="s.police_station">
											at {{ s.police_station }}</template
										>
										<template v-if="s.waiting_days > 30">
											·
											<b class="text-amber-700"
												>waiting {{ s.waiting_days }} days</b
											></template
										>
									</template>
									<template v-else>
										·
										{{
											[
												s.police_verification,
												s.verified_on && shortDate(s.verified_on),
											]
												.filter(Boolean)
												.join(" ")
										}}
									</template>
								</p>
							</div>
							<Button
								v-if="group.key === 'overdue' || group.key === 'pending'"
								size="sm"
								variant="ghost"
								:icon="Printer"
								:href="formUrl(s)"
								target="_blank"
								>Form</Button
							>
							<Button
								size="sm"
								:variant="group.key === 'done' ? 'ghost' : 'primary'"
								@click="openDialog('verification', { stay: s })"
								>{{
									group.key === "submitted"
										? "Mark verified"
										: group.key === "done"
										? "Change"
										: "Mark submitted"
								}}</Button
							>
						</li>
					</ul>
				</template>
			</section>
			<EmptyState
				v-if="data.enabled && !groups.some((g) => data[g.key].length)"
				:icon="ShieldCheck"
				title="Nothing to verify yet"
				description="New tenants show up here when they move in."
			/>
		</template>
	</div>
</template>

<script setup>
import { AlarmClock, Clock, FileText, Printer, ShieldCheck } from "lucide-vue-next";
import { ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import { openDialog } from "@/dialogs";
import { canUse, scope, toast } from "@/store";
import { useResource } from "@/useResource";
import { shortDate } from "@/utils";

const { data, reload } = useResource(() => get("get_verifications", scope()));
const groups = [
	{ key: "overdue", label: "Overdue" },
	{ key: "pending", label: "To submit" },
	{ key: "submitted", label: "With the police" },
	{ key: "done", label: "Done" },
];
const formUrl = (s) =>
	`/api/method/rent_management.api.download_verification_form?allotment=${encodeURIComponent(
		s.name
	)}`;

const enabling = ref(false);
async function enable() {
	if (!canUse()) return toast("Ask your manager to turn this on in Settings", "error");
	enabling.value = true;
	try {
		await post("save_settings", { data: { police_verification_enabled: 1 } });
		toast("Tracking is on for new tenants");
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		enabling.value = false;
	}
}
</script>
