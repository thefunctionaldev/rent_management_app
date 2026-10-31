<template>
	<div>
		<PageHeader
			:title="statement ? statement.bank || 'Bank statement' : 'Bank statements'"
			:subtitle="
				statement
					? `${date(statement.from_date)} to ${date(statement.to_date)} · ${
							statement.file_name
					  }`
					: 'Upload your bank or UPI statement and confirm the rent in it in one go'
			"
		>
			<template v-if="statement">
				<Button :icon="ArrowLeft" @click="$router.push('/bank-statements')">All</Button>
				<Button :icon="RefreshCw" :loading="rematching" @click="rematch"
					>Match again</Button
				>
			</template>
			<Button v-else variant="primary" :icon="Upload" @click="picker.click()"
				>Upload statement</Button
			>
			<input
				ref="picker"
				type="file"
				accept=".csv,.xls,.xlsx,.txt"
				class="sr-only"
				@change="upload"
			/>
		</PageHeader>

		<!-- the list -->
		<template v-if="!name">
			<div v-if="uploading" class="card mb-4 flex items-center gap-3 p-5 text-sm">
				<Loader2 class="size-5 animate-spin text-brand-600" /> Reading {{ uploading }} and
				matching it to your tenants' bills…
			</div>
			<div v-if="!list" class="space-y-3">
				<Skeleton class="h-20" /><Skeleton class="h-20" />
			</div>
			<div v-else-if="!list.length" class="card">
				<EmptyState
					:icon="Landmark"
					title="No statements yet"
					description="Download your account statement from your bank's website or app (Excel or CSV) and upload it. Rent that came in is matched to your tenants' bills for you to confirm."
				>
					<Button variant="primary" :icon="Upload" @click="picker.click()"
						>Upload statement</Button
					>
				</EmptyState>
			</div>
			<div v-else class="card divide-y divide-slate-100">
				<RouterLink
					v-for="s in list"
					:key="s.name"
					:to="`/bank-statements/${s.name}`"
					class="flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50"
				>
					<span
						class="grid size-10 place-items-center rounded-xl bg-slate-100 text-slate-500"
						><Landmark class="size-5"
					/></span>
					<div class="min-w-0 flex-1">
						<p class="font-medium">
							{{ s.bank || s.file_name }}
						</p>
						<p class="text-xs text-slate-500">
							{{ date(s.from_date) }} to {{ date(s.to_date) }} ·
							{{ s.credits }} credits · {{ money(s.total_credits) }} · uploaded
							{{ date(s.creation.slice(0, 10)) }}
						</p>
					</div>
					<span
						v-if="s.counts.Suggested"
						class="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"
						>{{ s.counts.Suggested }} to confirm</span
					>
					<span
						v-if="s.counts.Unmatched"
						class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
						>{{ s.counts.Unmatched }} not matched</span
					>
					<span
						v-if="s.confirmed"
						class="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700"
						>{{ s.confirmed }} confirmed</span
					>
					<ChevronRight class="size-5 text-slate-400" />
				</RouterLink>
			</div>
			<p class="mt-4 text-xs text-slate-400">
				Works with statements from most banks (HDFC, SBI, ICICI, Axis, Kotak and others)
				and UPI apps. Only money that came in is read; payments out are skipped.
			</p>
		</template>

		<!-- one statement -->
		<template v-else>
			<div v-if="!statement" class="space-y-3">
				<Skeleton class="h-24" /><Skeleton class="h-72" />
			</div>
			<template v-else>
				<div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					<StatCard
						label="Money in"
						:icon="Landmark"
						:value="money(statement.total_credits)"
						:hint="`${statement.credits} credits${
							statement.debits ? ` · ${statement.debits} payments out skipped` : ''
						}`"
					/>
					<StatCard
						label="To confirm"
						:icon="ListChecks"
						:value="money(total(groups.suggested))"
						:hint="`${groups.suggested.length} matched to rent`"
					/>
					<StatCard
						label="Not matched"
						:icon="CircleHelp"
						:value="money(total(groups.unmatched))"
						:hint="`${groups.unmatched.length} to pick or skip`"
					/>
					<StatCard
						label="Done"
						:icon="CircleCheck"
						:value="money(total(groups.done))"
						:hint="`${groups.done.length} confirmed or already recorded`"
					/>
				</div>

				<Tabs v-model="tab" :tabs="tabs" class="mb-4" />

				<!-- suggestions -->
				<div v-if="tab === 'suggested'">
					<div v-if="!groups.suggested.length" class="card">
						<EmptyState :icon="CircleCheck" title="Nothing to confirm" />
					</div>
					<div v-else class="card divide-y divide-slate-100 pb-20 sm:pb-0">
						<label
							class="flex items-center gap-3 px-5 py-3 text-xs font-medium text-slate-500"
						>
							<input
								type="checkbox"
								class="size-4 accent-brand-600"
								:checked="allChosen"
								@change="chooseAll($event.target.checked)"
							/>
							Choose all
						</label>
						<div
							v-for="l in groups.suggested"
							:key="l.name"
							class="flex flex-wrap items-start gap-3 px-5 py-3"
						>
							<input
								v-model="chosen"
								type="checkbox"
								:value="l.name"
								class="mt-1 size-4 accent-brand-600"
							/>
							<div class="min-w-0 flex-1">
								<div class="flex flex-wrap items-baseline gap-x-2">
									<span class="tabular font-semibold">{{
										money(l.amount)
									}}</span>
									<span class="text-xs text-slate-500">{{
										date(l.line_date)
									}}</span>
									<span
										class="rounded-full px-1.5 py-px text-[11px] font-medium"
										:class="
											l.confidence === 'High'
												? 'bg-emerald-50 text-emerald-700'
												: 'bg-amber-50 text-amber-700'
										"
										>{{ l.confidence === "High" ? "Sure" : "Check" }}</span
									>
								</div>
								<p class="truncate text-xs text-slate-400" :title="l.description">
									{{ l.description }}
								</p>
								<p class="mt-1 text-sm">
									→ <b>{{ l.tenant_name }}</b
									><span v-if="l.bill" class="text-slate-500">
										· {{ l.bill }}</span
									>
								</p>
								<p class="text-xs text-slate-500">Because {{ l.match_reason }}</p>
							</div>
							<div class="flex gap-1">
								<Button size="sm" variant="ghost" @click="editing = editLine(l)"
									>Change</Button
								>
								<Button
									size="sm"
									variant="ghost"
									@click="setLine(l, { status: 'Ignored' })"
									>Not rent</Button
								>
							</div>
						</div>
					</div>
					<div
						v-if="groups.suggested.length"
						class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 p-3 backdrop-blur sm:static sm:mt-4 sm:border-0 sm:bg-transparent sm:p-0"
					>
						<Button
							variant="primary"
							size="lg"
							class="w-full sm:w-auto"
							:icon="CircleCheck"
							:loading="confirming"
							:disabled="!chosen.length"
							@click="confirm"
							>{{
								chosen.length
									? `Confirm ${chosen.length} payment${
											chosen.length === 1 ? "" : "s"
									  } · ${money(chosenTotal)}`
									: "Tick the payments to confirm"
							}}</Button
						>
					</div>
				</div>

				<!-- not matched -->
				<div v-else-if="tab === 'unmatched'">
					<div v-if="!groups.unmatched.length" class="card">
						<EmptyState :icon="CircleCheck" title="Everything is matched" />
					</div>
					<div v-else class="card divide-y divide-slate-100">
						<div
							v-for="l in groups.unmatched"
							:key="l.name"
							class="flex flex-wrap items-start gap-3 px-5 py-3"
						>
							<div class="min-w-0 flex-1">
								<p>
									<span class="tabular font-semibold">{{
										money(l.amount)
									}}</span>
									<span class="ml-2 text-xs text-slate-500">{{
										date(l.line_date)
									}}</span>
								</p>
								<p class="text-xs break-words text-slate-500">
									{{ l.description }}
								</p>
								<p v-if="l.tenant_name" class="mt-1 text-xs text-slate-500">
									Looks like {{ l.tenant_name }} ({{ l.match_reason }})
								</p>
							</div>
							<div class="flex gap-1">
								<Button size="sm" @click="editing = editLine(l)"
									>Pick tenant</Button
								>
								<Button
									size="sm"
									variant="ghost"
									@click="setLine(l, { status: 'Ignored' })"
									>Not rent</Button
								>
							</div>
						</div>
					</div>
				</div>

				<!-- done and ignored -->
				<div v-else class="card divide-y divide-slate-100">
					<p v-if="!shown.length" class="px-5 py-8 text-center text-sm text-slate-400">
						Nothing here.
					</p>
					<div
						v-for="l in shown"
						:key="l.name"
						class="flex flex-wrap items-center gap-3 px-5 py-3"
					>
						<div class="min-w-0 flex-1">
							<p>
								<span class="tabular font-semibold">{{ money(l.amount) }}</span>
								<span class="ml-2 text-xs text-slate-500">{{
									date(l.line_date)
								}}</span>
								<span v-if="l.tenant_name" class="ml-2 text-sm"
									>· {{ l.tenant_name }}</span
								>
							</p>
							<p class="truncate text-xs text-slate-400">{{ l.description }}</p>
						</div>
						<StatusBadge
							:status="l.status === 'Already Recorded' ? 'Recorded' : l.status"
						/>
						<Button
							v-if="l.status === 'Ignored'"
							size="sm"
							variant="ghost"
							@click="setLine(l, { status: 'Unmatched' })"
							>Undo</Button
						>
					</div>
				</div>

				<div class="mt-8 flex justify-end">
					<Button variant="ghost" :icon="Trash2" @click="remove"
						>Delete this upload</Button
					>
				</div>
			</template>
		</template>

		<!-- pick the tenant -->
		<Modal
			v-if="editing"
			open
			title="Whose rent is this?"
			:subtitle="`${money(editing.line.amount)} on ${date(editing.line.line_date)}`"
			@close="editing = null"
		>
			<p class="mb-4 rounded-lg bg-slate-50 px-3 py-2 text-xs break-words text-slate-500">
				{{ editing.line.description }}
			</p>
			<Field label="Tenant">
				<select v-model="editing.tenant" class="input" @change="editing.bill = ''">
					<option value="">Choose…</option>
					<option v-for="t in statement.tenants" :key="t.tenant" :value="t.tenant">
						{{ t.tenant_name }} · {{ money(t.owed) }} unpaid
					</option>
				</select>
			</Field>
			<Field v-if="editingBills.length > 1" label="Bill" class="mt-4">
				<select v-model="editing.bill" class="input">
					<option value="">The oldest first</option>
					<option v-for="b in editingBills" :key="b.name" :value="b.name">
						{{ b.label }}
					</option>
				</select>
			</Field>
			<p
				v-if="editingOwed && editing.line.amount > editingOwed + 0.5"
				class="mt-3 text-xs text-rose-600"
			>
				That's more than they owe ({{ money(editingOwed) }}). Record the extra on the
				Payments page.
			</p>
			<p class="mt-3 text-xs text-slate-500">
				The name or UPI ID they paid from is remembered, so next time it matches by itself.
			</p>
			<template #footer>
				<Button @click="editing = null">Cancel</Button>
				<Button
					variant="primary"
					:disabled="!editing.tenant"
					@click="
						setLine(editing.line, {
							tenant: editing.tenant,
							rent_invoice: editing.bill,
						});
						editing = null;
					"
					>Match</Button
				>
			</template>
		</Modal>
	</div>
</template>

<script setup>
import {
	ArrowLeft,
	ChevronRight,
	CircleCheck,
	CircleHelp,
	Landmark,
	ListChecks,
	Loader2,
	RefreshCw,
	Trash2,
	Upload,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import EmptyState from "@/components/EmptyState.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import PageHeader from "@/components/PageHeader.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatCard from "@/components/StatCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Tabs from "@/components/Tabs.vue";
import { bumpData, toast } from "@/store";
import { useResource } from "@/useResource";
import { date, money } from "@/utils";

const props = defineProps({ name: { type: String, default: "" } });
const router = useRouter();

const { data: list } = useResource(() => get("get_bank_statements"));
const statement = ref(null);
async function load() {
	if (!props.name) return (statement.value = null);
	try {
		statement.value = await get("get_bank_statement", { name: props.name });
	} catch (e) {
		toast(e.message, "error");
	}
}
watch(() => props.name, load, { immediate: true });

const groups = computed(() => {
	const lines = statement.value?.lines || [];
	return {
		suggested: lines.filter((l) => l.status === "Suggested"),
		unmatched: lines.filter((l) => l.status === "Unmatched"),
		done: lines.filter((l) => ["Confirmed", "Already Recorded"].includes(l.status)),
		ignored: lines.filter((l) => l.status === "Ignored"),
	};
});
const total = (lines) => lines.reduce((sum, l) => sum + l.amount, 0);
const tab = ref("suggested");
const tabs = computed(() => [
	{ value: "suggested", label: "To confirm", count: groups.value.suggested.length },
	{ value: "unmatched", label: "Not matched", count: groups.value.unmatched.length },
	{ value: "done", label: "Done", count: groups.value.done.length },
	{ value: "ignored", label: "Not rent", count: groups.value.ignored.length },
]);
const shown = computed(() => groups.value[tab.value] || []);

// what to confirm: the sure ones are ticked to start with
const chosen = ref([]);
watch(
	() => statement.value?.name,
	() => {
		chosen.value = groups.value.suggested
			.filter((l) => l.confidence === "High")
			.map((l) => l.name);
	}
);
const allChosen = computed(
	() => groups.value.suggested.length && chosen.value.length === groups.value.suggested.length
);
function chooseAll(on) {
	chosen.value = on ? groups.value.suggested.map((l) => l.name) : [];
}
const chosenTotal = computed(() =>
	total(groups.value.suggested.filter((l) => chosen.value.includes(l.name)))
);

// upload
const picker = ref(null);
const uploading = ref("");
async function upload(event) {
	const file = event.target.files[0];
	event.target.value = "";
	if (!file) return;
	if (file.size > 10 * 1024 * 1024)
		return toast("That file is too big (10 MB at most)", "error");
	uploading.value = file.name;
	try {
		const content = await new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(reader.result);
			reader.onerror = reject;
			reader.readAsDataURL(file);
		});
		const bank = window.prompt("Which bank account is this? (optional)", "") || "";
		const name = await post("upload_bank_statement", { filename: file.name, content, bank });
		bumpData();
		router.push(`/bank-statements/${name}`);
	} catch (e) {
		toast(e.message, "error");
	} finally {
		uploading.value = "";
	}
}

// matching by hand
const editing = ref(null);
const editLine = (line) => ({ line, tenant: line.tenant ? String(line.tenant) : "", bill: "" });
const editingTenant = computed(() =>
	statement.value?.tenants.find((t) => String(t.tenant) === String(editing.value?.tenant))
);
const editingBills = computed(() => editingTenant.value?.bills || []);
const editingOwed = computed(() => editingTenant.value?.owed || 0);

async function setLine(line, args) {
	try {
		await post("set_bank_statement_line", { name: props.name, line: line.name, ...args });
		const keep = chosen.value;
		await load();
		chosen.value = args.tenant ? [...keep, line.name] : keep.filter((n) => n !== line.name);
	} catch (e) {
		toast(e.message, "error");
	}
}

const confirming = ref(false);
async function confirm() {
	confirming.value = true;
	try {
		const result = await post("confirm_bank_statement", {
			name: props.name,
			lines: chosen.value,
		});
		if (result.confirmed)
			toast(
				`${result.confirmed} payment${
					result.confirmed === 1 ? "" : "s"
				} recorded · ${money(result.amount)}`
			);
		for (const e of result.errors) toast(`${money(e.amount)}: ${e.error}`, "error");
		bumpData();
		await load();
		chosen.value = [];
	} catch (e) {
		toast(e.message, "error");
	} finally {
		confirming.value = false;
	}
}

const rematching = ref(false);
async function rematch() {
	rematching.value = true;
	try {
		await post("rematch_bank_statement", { name: props.name });
		await load();
		chosen.value = groups.value.suggested
			.filter((l) => l.confidence === "High")
			.map((l) => l.name);
		toast("Matched again");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		rematching.value = false;
	}
}

async function remove() {
	if (!window.confirm("Delete this upload? Payments already confirmed from it stay recorded."))
		return;
	try {
		await post("delete_bank_statement", { name: props.name });
		bumpData();
		router.push("/bank-statements");
	} catch (e) {
		toast(e.message, "error");
	}
}
</script>
