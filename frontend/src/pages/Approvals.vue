<template>
	<div>
		<PageHeader
			title="Approvals"
			subtitle="Review proposed financial changes before they take effect."
			><Button @click="reload">{{ $t("Refresh") }}</Button
			><Button v-if="data?.can_configure" @click="openRules"
				>Approval rules</Button
			></PageHeader
		>
		<p v-if="error" role="alert" class="mb-4 text-rose-700">{{ error }}</p>
		<p v-if="loading" role="status">Loading requests…</p>
		<p class="mb-4 text-sm text-slate-500">
			Latest 200 requests. Approving applies the change immediately. Payment reversal changes
			the ledger; it does not refund a payment through the bank or gateway.
		</p>
		<Field label="Status" class="mb-5 max-w-xs"
			><select v-model="status" class="input">
				<option value="">All statuses</option>
				<option>Pending</option>
				<option>Executed</option>
				<option>Rejected</option>
				<option>Withdrawn</option>
			</select></Field
		>
		<EmptyState
			v-if="!loading && !filtered.length"
			title="No requests here"
			description="Changes that reach a configured limit appear here automatically when saved in the Rent app."
		/>
		<div class="space-y-4">
			<article v-for="r in filtered" :key="r.name" class="card p-5">
				<div class="flex flex-wrap justify-between gap-3">
					<div>
						<h2 class="font-semibold">{{ r.action }} · {{ money(r.amount) }}</h2>
						<p class="mt-1 text-xs text-slate-500">
							{{ r.name }} · {{ r.property || "All buildings" }} ·
							{{ r.requested_by }}
						</p>
					</div>
					<StatusBadge :status="r.status" />
				</div>
				<p class="mt-3 text-sm text-slate-500">Reviewer role: {{ r.approver_role }}</p>
				<details class="my-3">
					<summary class="cursor-pointer text-sm text-brand-700">
						Review proposed values
					</summary>
					<dl class="mt-3 grid gap-2 rounded-xl bg-slate-50 p-4 text-sm">
						<div
							v-for="entry in details(r)"
							:key="entry.key"
							class="grid gap-1 sm:grid-cols-[12rem_1fr]"
						>
							<dt class="font-medium">{{ entry.key }}</dt>
							<dd class="whitespace-pre-wrap break-words">{{ entry.value }}</dd>
						</div>
					</dl>
				</details>
				<p v-if="r.decision_note" class="my-3 text-sm">{{ r.decision_note }}</p>
				<p v-if="r.result" class="my-3 text-sm text-emerald-700">
					Applied: {{ r.result }}
				</p>
				<div v-if="r.can_decide" class="flex flex-wrap gap-2">
					<Button variant="primary" :disabled="busy" @click="review(r, 'approve')"
						>Review and approve</Button
					><Button :disabled="busy" @click="review(r, 'reject')">{{
						$t("Reject")
					}}</Button>
				</div>
				<Button
					v-if="r.status === 'Pending' && r.requested_by === boot.user"
					:disabled="busy"
					@click="withdraw(r)"
					>Withdraw request</Button
				>
			</article>
		</div>
		<Modal
			v-if="reviewing"
			open
			:title="decision === 'approve' ? 'Approve and apply change' : 'Reject request'"
			@close="reviewing = null"
		>
			<p class="mb-4 text-sm">
				{{ reviewing.action }} · {{ money(reviewing.amount) }} · {{ reviewing.name }}
			</p>
			<p v-if="decision === 'approve'" class="mb-4 text-sm text-slate-500">
				This applies the proposed values immediately using the requester's current
				permissions. Check the details before continuing.
			</p>
			<Field :label="decision === 'reject' ? 'Reason (required)' : 'Review note (optional)'">
				<textarea v-model="note" class="input" rows="3" />
			</Field>
			<template #footer
				><Button :disabled="busy" @click="reviewing = null">Back</Button
				><Button
					variant="primary"
					:loading="busy"
					:disabled="decision === 'reject' && !note.trim()"
					@click="decide"
					>{{ decision === "approve" ? "Approve and apply" : "Reject request" }}</Button
				></template
			>
		</Modal>
		<Modal
			v-if="rulesOpen"
			open
			title="Approval rules"
			subtitle="System Managers only. Changes at or above a limit require another person."
			width="lg"
			@close="rulesOpen = false"
		>
			<label class="flex items-center gap-2 text-sm"
				><input v-model="rules.enabled" type="checkbox" />Enable financial approvals</label
			>
			<p class="my-4 text-sm text-slate-500">
				A limit of zero covers every amount. If multiple requester roles match, the lowest
				limit wins. Ensure another active user has the approver role before enabling.
				Existing pending requests still require review.
			</p>
			<div
				v-for="(r, i) in rules.rules"
				:key="i"
				class="mb-4 grid gap-3 rounded-2xl border border-slate-200 p-4 sm:grid-cols-2"
			>
				<Field label="Action"
					><select v-model="r.action" class="input">
						<option v-for="a in actions" :key="a">{{ a }}</option>
					</select></Field
				>
				<Field label="Requester role"
					><select v-model="r.requester_role" class="input">
						<option>Rent Staff</option>
						<option>Rent Manager</option>
						<option>System Manager</option>
					</select></Field
				>
				<Field label="Amount limit"
					><input
						v-model.number="r.threshold"
						type="number"
						min="0"
						step="0.01"
						class="input"
				/></Field>
				<Field label="Approver role"
					><select v-model="r.approver_role" class="input">
						<option>Rent Manager</option>
						<option>System Manager</option>
					</select></Field
				>
				<Button variant="ghost" @click="rules.rules.splice(i, 1)">Remove rule</Button>
			</div>
			<Button
				@click="
					rules.rules.push({
						action: 'Expense',
						requester_role: 'Rent Staff',
						threshold: 5000,
						approver_role: 'Rent Manager',
					})
				"
				>Add rule</Button
			>
			<template #footer
				><Button @click="rulesOpen = false">{{ $t("Cancel") }}</Button
				><Button variant="primary" :loading="saving" @click="saveRules"
					>Save rules</Button
				></template
			>
		</Modal>
	</div>
</template>
<script setup>
import { computed, reactive, ref } from "vue";
import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import EmptyState from "@/components/EmptyState.vue";
import PageHeader from "@/components/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { boot, toast } from "@/store";
import { useAction, useResource } from "@/useResource";
import { money } from "@/utils";
const { data, loading, error, reload } = useResource(() => get("get_approvals"));
const status = ref("Pending"),
	reviewing = ref(null),
	decision = ref("approve"),
	note = ref("");
const filtered = computed(() =>
	(data.value?.requests || []).filter((r) => !status.value || r.status === status.value)
);
function details(r) {
	try {
		let p = JSON.parse(r.payload);
		if (p.data) p = typeof p.data === "string" ? JSON.parse(p.data) : p.data;
		return Object.entries(p).map(([key, value]) => ({
			key: key.replaceAll("_", " "),
			value:
				typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "—"),
		}));
	} catch {
		return [{ key: "Details", value: "Unable to read this request. Do not approve." }];
	}
}
function review(r, d) {
	reviewing.value = r;
	decision.value = d;
	note.value = "";
}
const { loading: busy, run } = useAction((method, args) => post(method, args), {
	success: "Request updated",
});
async function decide() {
	await run("decide_approval", {
		name: reviewing.value.name,
		decision: decision.value,
		note: note.value,
	});
	reviewing.value = null;
}
async function withdraw(r) {
	await run("withdraw_approval", { name: r.name });
}
const rulesOpen = ref(false),
	rules = reactive({ enabled: false, rules: [] });
const actions = ["Expense", "Deposit refund", "Invoice discount", "Payment reversal"];
async function openRules() {
	try {
		Object.assign(rules, await get("get_approval_rules"));
		rules.enabled = !!rules.enabled;
		rulesOpen.value = true;
	} catch (e) {
		toast(e.message, "error");
	}
}
const { loading: saving, run: save } = useAction(
	() => post("save_approval_rules", { data: { ...rules, enabled: rules.enabled ? 1 : 0 } }),
	{ success: "Approval rules saved" }
);
async function saveRules() {
	await save();
	rulesOpen.value = false;
}
</script>
