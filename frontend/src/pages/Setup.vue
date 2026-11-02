<template>
	<div>
		<PageHeader
			title="Make yourself at home"
			subtitle="Set up your property, one step at a time. Progress is saved as you work."
			><Button @click="reload">Refresh progress</Button></PageHeader
		>
		<p v-if="error" role="alert" class="mb-4 text-rose-700">{{ error }}</p>
		<p v-if="loading && !data" role="status">Loading your setup…</p>
		<template v-if="data">
			<div class="card mb-6 p-6">
				<div class="flex justify-between text-sm">
					<strong>{{ done }} of 5 steps complete</strong
					><span>{{
						done === 5
							? "Ready to manage your property"
							: "Your workspace is taking shape"
					}}</span>
				</div>
				<progress
					:value="done"
					max="5"
					class="mt-4 h-2 w-full accent-brand-600"
					aria-label="Setup progress"
				/>
			</div>
			<div class="grid gap-6 lg:grid-cols-[19rem_1fr]">
				<nav aria-label="Setup steps" class="space-y-2">
					<button
						v-for="(step, index) in data.steps"
						:key="step.key"
						class="flex w-full items-center gap-3 rounded-2xl p-4 text-left text-sm"
						:class="
							selected === step.key
								? 'bg-brand-600 text-white'
								: 'bg-white text-slate-700'
						"
						:aria-current="selected === step.key ? 'step' : undefined"
						@click="selected = step.key"
					>
						<span
							class="grid size-8 shrink-0 place-items-center rounded-full bg-black/5"
							>{{ step.done ? "✓" : index + 1 }}</span
						>{{ step.title }}<span v-if="step.done" class="sr-only">{{ $t("Completed") }}</span>
					</button>
				</nav>
				<section class="card p-6 sm:p-8">
					<h2 class="text-xl font-semibold">{{ active?.title }}</h2>
					<p class="my-4 text-sm leading-6 text-slate-500">
						{{ descriptions[selected] }}
					</p>
					<template v-if="selected === 'rules'">
						<form class="grid gap-4 sm:grid-cols-2" @submit.prevent="saveRules">
							<Field label="Landlord name"
								><input v-model="form.landlord_name" class="input"
							/></Field>
							<Field label="Phone"
								><input v-model="form.landlord_phone" class="input"
							/></Field>
							<Field label="Rent due day (1–28)"
								><input
									v-model.number="form.rent_due_day"
									class="input"
									type="number"
									min="1"
									max="28"
									required
							/></Field>
							<Field label="Agreement term (months)"
								><input
									v-model.number="form.default_agreement_months"
									class="input"
									type="number"
									min="1"
									required
							/></Field>
							<Field label="Notice period (days)"
								><input
									v-model.number="form.default_notice_days"
									class="input"
									type="number"
									min="0"
									required
							/></Field>
							<Field label="UPI ID (optional)"
								><input
									v-model="form.upi_id"
									class="input"
									placeholder="yourname@bank"
							/></Field>
							<p class="text-sm text-slate-500 sm:col-span-2">
								Cash and bank transfer work without online setup. Configure
								Razorpay and reminders in
								<RouterLink to="/settings" class="text-brand-600 underline"
									>{{ $t("Settings") }}</RouterLink
								>.
							</p>
							<Button variant="primary" type="submit" :loading="saving"
								>Save and continue</Button
							>
						</form>
					</template>
					<template v-else>
						<Button
							variant="primary"
							:disabled="
								(selected !== 'building' && !data.counts.buildings) ||
								(selected === 'allotment' &&
									(!data.counts.rooms || !data.counts.tenants))
							"
							@click="openDialog(actions[selected])"
							>{{ labels[selected] }}</Button
						>
						<p v-if="active?.done" class="mt-4 text-sm text-emerald-700">
							This step is complete. You can add more whenever you need.
						</p>
					</template>
					<div class="mt-8 flex justify-between border-t border-slate-100 pt-5">
						<Button
							:disabled="index === 0"
							@click="selected = data.steps[index - 1].key"
							>Back</Button
						>
						<Button v-if="index < 4" @click="selected = data.steps[index + 1].key"
							>Next step</Button
						>
						<RouterLink v-else to="/" class="text-sm font-semibold text-brand-600"
							>Go to dashboard →</RouterLink
						>
					</div>
				</section>
			</div>
		</template>
	</div>
</template>
<script setup>
import { computed, reactive, ref, watch } from "vue";
import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import PageHeader from "@/components/PageHeader.vue";
import { openDialog } from "@/dialogs";
import { useAction, useResource } from "@/useResource";
const { data, loading, error, reload } = useResource(() => get("get_setup_progress"));
const selected = ref("building");
const form = reactive({ rent_due_day: 5, default_agreement_months: 11, default_notice_days: 30 });
let initialized = false;
watch(data, (value) => {
	if (value && !initialized) {
		Object.assign(form, value.settings);
		selected.value = value.steps.find((s) => !s.done)?.key || "building";
		initialized = true;
	}
});
const done = computed(() => data.value?.steps.filter((s) => s.done).length || 0);
const index = computed(() => data.value?.steps.findIndex((s) => s.key === selected.value) ?? 0);
const active = computed(() => data.value?.steps[index.value]);
const descriptions = {
	building:
		"Add the building name and address. Each building keeps its rooms, expenses and reports together.",
	rooms: "Create a private room or shared room with its bed capacity, rent and deposit. Existing room types can be reused.",
	rules: "Review your defaults and how tenants can pay. These settings apply to new agreements.",
	tenant: "Create a tenant profile using their name and contact details.",
	allotment:
		"Select a tenant and room to start their stay. The existing availability and agreement checks still apply.",
};
const actions = { building: "property", rooms: "room", tenant: "tenant", allotment: "allotRoom" };
const labels = {
	building: "Add building",
	rooms: "Add room",
	tenant: "Add tenant",
	allotment: "Allot a room",
};
const { loading: saving, run } = useAction(() => post("save_setup_rules", { data: form }), {
	success: "Rent defaults saved",
});
async function saveRules() {
	await run();
	selected.value = "tenant";
}
</script>
