<template>
	<div class="space-y-6">
		<header class="flex justify-between gap-4">
			<div>
				<h1 class="text-3xl font-semibold">{{ $t("ERPNext integration") }}</h1>
				<p class="mt-2 text-slate-500">
					{{
						$t("Send accounting drafts for review. Nothing is submitted automatically.")
					}}
				</p>
			</div>
			<Button :loading="busy" @click="load">{{ $t("Refresh") }}</Button>
		</header>
		<p v-if="error" role="alert" class="text-rose-600">{{ error }}</p>
		<p v-if="notice" role="status">{{ $t(notice) }}</p>
		<template v-if="data"
			><section class="card space-y-3 p-5">
				<div class="flex items-center justify-between">
					<h2 class="font-semibold">
						{{
							$t(data.settings.enabled ? "Connection enabled" : "Connection disabled")
						}}
					</h2>
					<Button v-if="data.can_configure" @click="configure">{{
						$t("Configure")
					}}</Button>
				</div>
				<p class="text-sm text-slate-500">
					{{
						$t(
							"Requires matching currencies and unique custom_rent_sync_key fields on Customer, Sales Invoice, Payment Entry, and Journal Entry in ERPNext. Submit the remote invoice before syncing its payment.",
						)
					}}
				</p>
				<p class="text-sm text-slate-500">
					{{
						$t(
							"Deposit collections use the configured bank account. Check it before submission. Refunds, transfers, cancellations, taxes, and later source edits require manual reconciliation.",
						)
					}}
				</p>
			</section>
			<form class="card space-y-4 p-5" @submit.prevent="queue">
				<h2 class="font-semibold">{{ $t("Queue a document") }}</h2>
				<label class="block"
					><span class="label">{{ $t("Source type") }}</span
					><select v-model="source.source_doctype" class="input" required>
						<option v-for="s in data.source_types" :key="s">{{ s }}</option>
					</select></label
				><label class="block"
					><span class="label">{{ $t("Source document ID") }}</span
					><input v-model="source.source_name" class="input" required /></label
				><Button
					type="submit"
					variant="primary"
					:disabled="busy || !data.settings.enabled"
					>{{ $t("Queue draft sync") }}</Button
				>
				<p class="text-sm text-slate-500">
					{{
						$t(
							"Queued records run daily or through the erp-sync job in Operational health.",
						)
					}}
				</p>
			</form>
			<div class="space-y-3">
				<article v-for="r in data.rows" :key="r.name" class="card p-5">
					<div class="flex justify-between gap-3">
						<h2 class="font-semibold">{{ r.source_doctype }} · {{ r.source_name }}</h2>
						<span>{{ $t(r.status) }}</span>
					</div>
					<p class="mt-2 text-sm text-slate-500">
						{{ $t("Attempts") }}: {{ r.attempts }} · {{ r.last_attempt || "—" }}
					</p>
					<p v-if="r.remote_name" class="mt-2 text-sm">
						{{ r.remote_doctype }} / {{ r.remote_name }}
					</p>
					<p v-if="r.source_changed" class="mt-2 text-amber-700">
						{{ $t("Source changed. Reconcile manually before retrying.") }}
					</p>
					<p v-if="r.error" class="mt-2 text-sm text-rose-600">{{ r.error }}</p>
					<Button
						v-if="r.status === 'Failed' && !r.source_changed"
						class="mt-3"
						:disabled="busy"
						@click="retry(r)"
						>{{ $t("Retry") }}</Button
					>
				</article>
				<p v-if="!data.rows.length">{{ $t("No sync records yet.") }}</p>
			</div></template
		><EditForm v-if="dialog" v-bind="dialog" @close="dialog = null" @saved="saved" />
	</div>
</template>
<script setup>
import { ref, reactive, onMounted } from "vue";
import Button from "@/components/Button.vue";
import EditForm from "./EditForm.vue";
import { read, write } from "./shared";
const data = ref(null),
	error = ref(""),
	notice = ref(""),
	busy = ref(false),
	dialog = ref(null),
	source = reactive({ source_doctype: "Tenant Rent Invoice", source_name: "" });
async function load() {
	busy.value = true;
	error.value = "";
	try {
		data.value = await read("erp_sync.overview");
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
async function action(method, args) {
	busy.value = true;
	error.value = "";
	try {
		await write(method, args);
		notice.value = "Queued";
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
const queue = () => action("erp_sync.queue", { ...source });
const retry = (r) => action("erp_sync.retry", { name: r.name });
function configure() {
	const settings = data.value.settings;
	const keys = [
		"base_url",
		"company",
		"currency",
		"rent_item",
		"income_account",
		"expense_account",
		"deposit_account",
		"receivable_account",
		"bank_account",
		"cash_account",
		"cost_center",
		"customer_group",
		"territory",
	];
	dialog.value = {
		title: "Configure ERPNext",
		hint: "Credentials are stored encrypted. Leave password fields empty to retain saved credentials. Enabling validates the remote configuration.",
		fields: [
			{ key: "enabled", type: "checkbox" },
			...keys.map((key) => ({ key, type: key === "base_url" ? "url" : "text" })),
			{ key: "api_key", type: "password" },
			{ key: "api_secret", type: "password" },
		],
		initial: {
			currency: "INR",
			customer_group: "Individual",
			territory: "All Territories",
			...settings,
			api_key: "",
			api_secret: "",
		},
		save: (values) => write("erp_sync.configure", { data: values }),
	};
}
async function saved() {
	dialog.value = null;
	notice.value = "Settings saved";
	await load();
}
onMounted(load);
</script>
