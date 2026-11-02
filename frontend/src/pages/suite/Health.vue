<template>
	<div class="space-y-6">
		<header>
			<h1 class="text-3xl font-semibold">{{ $t("Operational health") }}</h1>
			<p class="mt-2 text-slate-500">
				{{ $t("Job history, delivery failures, and confirmed backup timestamps.") }}
			</p>
		</header>
		<p v-if="error" role="alert" class="text-rose-600">{{ error }}</p>
		<p v-if="notice" role="status">{{ $t(notice) }}</p>
		<Button :loading="busy" @click="load">{{ $t("Refresh") }}</Button
		><template v-if="data"
			><div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<div
					v-for="(value, key) in {
						'Overdue tasks': data.overdue_tasks,
						'Sync failures': data.sync_failures,
						'Last local backup': data.backup_at || 'Not recorded',
						'Last remote backup': data.remote_backup_at || 'Not recorded',
					}"
					:key="key"
					class="card p-5"
				>
					<p class="text-sm text-slate-500">{{ $t(key) }}</p>
					<p class="mt-2 font-semibold">{{ $t(String(value)) }}</p>
				</div>
			</div>
			<p class="text-sm text-slate-500">
				{{
					$t(
						"Backup timestamps cover the rent-backup-all command. They do not prove a backup can be restored.",
					)
				}}
			</p>
			<section v-if="data.can_retry" class="card p-5">
				<h2 class="mb-3 font-semibold">{{ $t("Run a job") }}</h2>
				<div class="flex flex-wrap gap-2">
					<Button
						v-for="job in data.jobs"
						:key="job"
						:disabled="busy"
						@click="retry(job)"
						>{{ job }}</Button
					>
				</div>
				<p class="mt-3 text-sm text-slate-500">
					{{
						$t(
							"Jobs run in the background. Refresh to see the result. Reminder jobs may send messages.",
						)
					}}
				</p>
			</section>
			<section class="card overflow-x-auto p-5">
				<h2 class="mb-4 font-semibold">{{ $t("Recent runs") }}</h2>
				<table class="w-full text-left text-sm">
					<thead>
						<tr>
							<th>{{ $t("Job") }}</th>
							<th>{{ $t("Status") }}</th>
							<th>{{ $t("Started") }}</th>
							<th>{{ $t("Result") }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="r in data.runs" :key="r.name" class="border-t border-slate-100">
							<td class="py-3 pr-3">{{ r.job_key }}</td>
							<td class="pr-3">{{ $t(r.status) }}</td>
							<td class="pr-3">{{ r.started_on }}</td>
							<td>{{ r.summary }}</td>
						</tr>
					</tbody>
				</table>
				<p v-if="!data.runs.length">{{ $t("No runs recorded yet.") }}</p>
			</section>
			<section class="card p-5">
				<h2 class="font-semibold">{{ $t("Failed messages · last 30 days") }}</h2>
				<p class="mt-2 text-sm text-slate-500">
					{{
						$t(
							"Review the invoice or payment before resending. A retry can notify the tenant again.",
						)
					}}
				</p>
				<div
					v-for="m in data.failed_messages"
					:key="m.name"
					class="flex justify-between gap-3 border-b border-slate-100 py-3 text-sm"
				>
					<span>{{ m.message_type }} · {{ m.channel }} · {{ m.creation }}</span
					><RouterLink v-if="m.rent_invoice" to="/invoices" class="text-brand-600">{{
						$t("Open invoices")
					}}</RouterLink>
				</div>
				<p v-if="!data.failed_messages.length" class="mt-3">
					{{ $t("No recent failures.") }}
				</p>
			</section></template
		>
	</div>
</template>
<script setup>
import { ref, onMounted } from "vue";
import Button from "@/components/Button.vue";
import { read, write } from "./shared";
const data = ref(null),
	busy = ref(false),
	error = ref(""),
	notice = ref("");
async function load() {
	busy.value = true;
	error.value = "";
	try {
		data.value = await read("health.overview");
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
async function retry(key) {
	if (!window.confirm(`Run ${key}? This may create due records or send scheduled reminders.`))
		return;
	busy.value = true;
	try {
		await write("health.retry", { key });
		notice.value = "Job queued";
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
onMounted(load);
</script>
