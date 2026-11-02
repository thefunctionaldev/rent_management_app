<template>
	<div class="min-h-screen bg-slate-50">
		<header class="border-b border-slate-200 bg-white/80 px-6 py-5 backdrop-blur">
			<div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
				<h1 class="text-xl font-semibold">{{ $t("Owner portal") }}</h1>
				<div class="flex items-center gap-4">
					<LanguageSwitcher /><a href="/logout" class="text-sm text-slate-500">{{
						$t("Log out")
					}}</a>
				</div>
			</div>
		</header>
		<main class="mx-auto max-w-6xl space-y-6 px-5 py-8">
			<div>
				<p class="text-sm text-slate-500">{{ $t("Your properties") }}</p>
				<h2 class="mt-1 text-3xl font-semibold">
					{{ $t("A clear view of your investment.") }}
				</h2>
			</div>
			<form class="flex flex-wrap items-end gap-3" @submit.prevent="load">
				<label
					><span class="label">{{ $t("Property") }}</span
					><select v-model="filter.property" class="input">
						<option value="">{{ $t("All properties") }}</option>
						<option v-for="p in properties" :key="p">{{ p }}</option>
					</select></label
				><label
					><span class="label">{{ $t("From date") }}</span
					><input v-model="filter.from_date" type="date" class="input" required /></label
				><label
					><span class="label">{{ $t("To date") }}</span
					><input v-model="filter.to_date" type="date" class="input" required /></label
				><Button type="submit" :loading="busy">{{ $t("Refresh") }}</Button>
			</form>
			<p v-if="error" role="alert" class="text-rose-600">{{ error }}</p>
			<template v-if="data"
				><p v-if="!data.summary.length" class="card p-8">
					{{ $t("No properties assigned. Ask your property manager for access.") }}
				</p>
				<article v-for="s in data.summary" :key="s.property" class="card p-6">
					<h3 class="text-xl font-semibold">{{ s.property }}</h3>
					<dl class="mt-5 grid grid-cols-2 gap-5 lg:grid-cols-5">
						<div
							v-for="k in ['collected', 'expenses', 'net_cash', 'outstanding']"
							:key="k"
						>
							<dt class="text-sm text-slate-500">{{ $t(label(k)) }}</dt>
							<dd class="mt-1 text-xl font-semibold">{{ money(s[k]) }}</dd>
						</div>
						<div>
							<dt class="text-sm text-slate-500">{{ $t("Occupied beds") }}</dt>
							<dd class="mt-1 text-xl font-semibold">
								{{ s.occupied }} / {{ s.beds }}
							</dd>
						</div>
					</dl>
				</article>
				<p class="text-sm text-slate-500">
					{{
						$t(
							"Collections and expenses cover the selected dates. Outstanding and occupancy show current totals. Deposit collections are excluded from rental cash flow.",
						)
					}}
				</p>
				<section>
					<h3 class="mb-4 text-xl font-semibold">{{ $t("Repairs and quotes") }}</h3>
					<div class="grid gap-4 md:grid-cols-2">
						<article v-for="r in data.work_orders" :key="r.name" class="card p-5">
							<div class="flex justify-between gap-3">
								<h4 class="font-semibold">{{ r.subject }}</h4>
								<span class="text-sm">{{ $t(r.status) }}</span>
							</div>
							<p class="mt-2 text-sm text-slate-500">
								{{ r.property }} · {{ r.due_date }}
							</p>
							<p class="mt-3">
								{{ $t("Quote amount") }}: {{ money(r.quote_amount) }}
							</p>
							<p v-if="r.completion_note" class="mt-2 text-sm">
								{{ r.completion_note }}
							</p>
							<p v-if="r.quote_note" class="mt-2 text-sm text-slate-500">
								{{ r.quote_note }}
							</p>
							<div v-if="r.status === 'Pending Approval'" class="mt-4 flex gap-2">
								<Button @click="review(r, true)">{{ $t("Approve") }}</Button
								><Button @click="review(r, false)">{{ $t("Reject") }}</Button>
							</div>
						</article>
					</div>
					<p v-if="!data.work_orders.length" class="text-sm text-slate-500">
						{{ $t("No repair orders yet.") }}
					</p>
				</section>
				<section class="card p-5">
					<h3 class="mb-3 font-semibold">{{ $t("Shared documents") }}</h3>
					<div
						v-for="d in data.documents"
						:key="d.name"
						class="border-t border-slate-100 py-3"
					>
						<a
							v-if="d.file"
							:href="download('Rent Owner Document', d.name, 'file')"
							class="text-brand-600 underline"
							>{{ d.title }}</a
						>
						<p v-else>{{ d.title }} · {{ $t("Upload pending") }}</p>
						<p class="text-sm text-slate-500">{{ d.property }} · {{ d.description }}</p>
					</div>
					<p v-if="!data.documents.length">{{ $t("No documents shared yet.") }}</p>
				</section></template
			>
		</main>
		<EditForm v-if="dialog" v-bind="dialog" @close="dialog = null" @saved="saved" />
	</div>
</template>
<script setup>
import { ref, reactive, onMounted } from "vue";
import Button from "@/components/Button.vue";
import EditForm from "@/pages/suite/EditForm.vue";
import LanguageSwitcher from "@/components/LanguageSwitcher.vue";
import { read, write, download, title as label } from "@/pages/suite/shared";
const data = ref(null),
	properties = ref([]),
	busy = ref(false),
	error = ref(""),
	dialog = ref(null);
const now = new Date();
const day = now.toLocaleDateString("en-CA");
const filter = reactive({ property: "", from_date: day.slice(0, 7) + "-01", to_date: day });
const money = (n) => new Intl.NumberFormat(undefined, { style: "currency", currency: data.value?.currency || "INR", maximumFractionDigits: 2 }).format(n || 0);
async function load() {
	busy.value = true;
	error.value = "";
	try {
		data.value = await read("owners.dashboard", filter);
		if (!filter.property) properties.value = data.value.properties;
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
function review(r, approve) {
	dialog.value = {
		title: approve ? "Approve quote" : "Reject quote",
		hint: `${r.subject} · ${money(r.quote_amount)}`,
		fields: [{ key: "note", type: "textarea", required: !approve }],
		initial: {},
		save: (v) => write("owners.review_quote", { name: r.name, approve: approve ? 1 : 0, ...v }),
	};
}
async function saved() {
	dialog.value = null;
	await load();
}
onMounted(load);
</script>
