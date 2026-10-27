<template>
	<Modal
		open
		width="lg"
		:title="lead ? lead.lead_name : 'Add lead'"
		:subtitle="
			lead
				? [lead.mobile_no, lead.property, lead.source].filter(Boolean).join(' · ')
				: 'A walk-in, phone call or referral'
		"
		@close="$emit('close')"
	>
		<div v-if="name && !lead" class="space-y-3">
			<Skeleton v-for="i in 4" :key="i" class="h-10" />
		</div>
		<form v-else id="lead-form" class="space-y-5" @submit.prevent="save">
			<div v-if="lead" class="flex flex-wrap items-center gap-2">
				<StatusBadge :status="lead.status" />
				<Button size="sm" :icon="Phone" :href="`tel:${lead.mobile_no}`">Call</Button>
				<Button size="sm" :icon="MessageCircle" :href="whatsapp()" target="_blank"
					>WhatsApp</Button
				>
				<span class="ml-auto text-xs text-slate-500"
					>Came in {{ date(lead.creation.slice(0, 10)) }}</span
				>
			</div>
			<p v-if="lead?.message" class="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
				“{{ lead.message }}”
			</p>

			<div v-if="!lead" class="grid gap-4 sm:grid-cols-2">
				<Field label="Name" required>
					<input v-model="form.lead_name" class="input" required autofocus />
				</Field>
				<Field label="Mobile number" required>
					<input v-model="form.mobile_no" class="input" type="tel" required />
				</Field>
				<Field label="Email">
					<input v-model="form.email_id" class="input" type="email" />
				</Field>
				<Field label="Came through">
					<select v-model="form.source" class="input">
						<option v-for="s in sources" :key="s">{{ s }}</option>
					</select>
				</Field>
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Building" required>
					<select v-model="form.property" class="input" required :disabled="moved">
						<option v-for="p in activeProperties()" :key="p.name" :value="p.name">
							{{ p.name }}
						</option>
					</select>
				</Field>
				<Field label="Room type">
					<select v-model="form.room_type" class="input" :disabled="moved">
						<option value="">Any</option>
						<option v-for="t in roomTypes" :key="t.name" :value="t.name">
							{{ t.name }}
						</option>
					</select>
				</Field>
				<Field label="Moving in">
					<input
						v-model="form.move_in_date"
						class="input"
						type="date"
						:disabled="moved"
					/>
				</Field>
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Status">
					<select v-model="form.status" class="input" :disabled="moved">
						<option v-for="s in statuses" :key="s">{{ s }}</option>
					</select>
				</Field>
				<Field label="Visit">
					<input
						v-model="form.visit_on"
						class="input"
						type="datetime-local"
						:disabled="moved"
					/>
				</Field>
				<Field v-if="form.status === 'Lost'" label="Why">
					<input
						v-model="form.lost_reason"
						class="input"
						list="lost-reasons"
						placeholder="Too far, budget..."
					/>
					<datalist id="lost-reasons">
						<option v-for="r in lostReasons" :key="r" :value="r" />
					</datalist>
				</Field>
			</div>
			<Field label="Notes" hint="Only managers see these">
				<textarea v-model="form.notes" class="input" rows="2" />
			</Field>

			<!-- token -->
			<div v-if="lead && !moved" class="rounded-xl border border-slate-200 p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<p class="text-sm font-medium">Token to hold a bed</p>
						<p class="text-xs text-slate-500">
							<template v-if="lead.token_status === 'Paid'"
								>{{ money(lead.token_amount) }} paid on
								{{ date(lead.token_paid_on) }} ({{ lead.token_mode
								}}{{ lead.token_reference ? ` · ${lead.token_reference}` : "" }}).
								It counts towards their rent.</template
							>
							<template v-else-if="lead.token_status === 'Reported'"
								>They say they paid {{ money(lead.token_amount) }} by UPI
								<b>{{ lead.token_reference || "" }}</b
								>. Check your UPI app, then confirm.</template
							>
							<template v-else-if="lead.token_status === 'Pending'"
								>Asked for {{ money(lead.token_amount) }}, not paid yet.</template
							>
							<template v-else>No token yet.</template>
						</p>
					</div>
					<StatusBadge v-if="lead.token_status" :status="`Token ${lead.token_status}`" />
				</div>
				<div v-if="lead.token_status !== 'Paid'" class="mt-3 grid gap-3 sm:grid-cols-4">
					<input
						v-model="token.amount"
						class="input tabular"
						type="number"
						min="1"
						placeholder="Amount"
					/>
					<select v-model="token.mode" class="input">
						<option>Cash</option>
						<option>UPI</option>
						<option>Bank Transfer</option>
						<option>Other</option>
					</select>
					<input v-model="token.reference" class="input" placeholder="Reference" />
					<Button :loading="recording" @click="recordToken">{{
						lead.token_status === "Reported" ? "Confirm" : "Record"
					}}</Button>
				</div>
				<div
					v-if="lead.token_status !== 'Paid'"
					class="mt-3 flex flex-wrap items-center gap-2"
				>
					<Button size="sm" :icon="Send" :loading="asking" @click="askForToken"
						>Send booking link</Button
					>
					<span class="text-xs text-slate-500"
						>They pay online or by UPI from the link, and the bed is held.</span
					>
				</div>
			</div>

			<p v-if="moved" class="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
				Moved in to room {{ lead.room }}.
				<RouterLink
					:to="`/tenants/${lead.tenant}`"
					class="font-medium underline"
					@click="$emit('close')"
					>Open their profile</RouterLink
				>
			</p>
		</form>
		<template #footer>
			<Button
				v-if="lead && !moved"
				variant="ghost"
				class="mr-auto"
				:icon="KeyRound"
				@click="openDialog('moveInLead', { lead })"
				>Move in</Button
			>
			<Button @click="$emit('close')">{{ moved ? "Close" : "Cancel" }}</Button>
			<Button
				v-if="!moved"
				variant="primary"
				type="submit"
				form="lead-form"
				:loading="loading"
				>{{ lead ? "Save" : "Add lead" }}</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { KeyRound, MessageCircle, Phone, Send } from "lucide-vue-next";
import { computed, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDialog } from "@/dialogs";
import { activeProperties, bumpData, toast, ui } from "@/store";
import { useAction, useResource } from "@/useResource";
import { date, money } from "@/utils";

const props = defineProps({ name: { type: String, default: null } });
const emit = defineEmits(["close"]);

const statuses = ["New", "Contacted", "Visit Scheduled", "Visited", "Booked", "Lost"];
const sources = ["Walk-in", "Phone", "Referral", "Broker", "Listing", "Other"];
const lostReasons = [
	"Too far",
	"Over budget",
	"Found another place",
	"No reply",
	"Room not liked",
];
const fields = [
	"lead_name",
	"mobile_no",
	"email_id",
	"source",
	"property",
	"room_type",
	"move_in_date",
	"status",
	"visit_on",
	"lost_reason",
	"notes",
];

const lead = ref(null);
const form = reactive({
	lead_name: "",
	mobile_no: "",
	email_id: "",
	source: "Walk-in",
	property: ui.property || activeProperties()[0]?.name || "",
	room_type: "",
	move_in_date: "",
	status: "New",
	visit_on: "",
	lost_reason: "",
	notes: "",
});
const token = reactive({ amount: "", mode: "Cash", reference: "" });
const moved = computed(() => lead.value?.status === "Moved In");
const roomTypes = useResource(() => get("get_room_types"), { initial: [] }).data;

async function load() {
	const data = await get("get_lead", { name: props.name });
	lead.value = data;
	for (const f of fields) form[f] = data[f] ?? "";
	form.visit_on = data.visit_on ? data.visit_on.slice(0, 16).replace(" ", "T") : "";
	token.amount = data.token_amount || "";
	if (data.token_status === "Reported") token.mode = "UPI";
	token.reference = data.token_reference || "";
}
if (props.name) load();

const { loading, run } = useAction((data) => post("save_lead", { data }), {
	success: props.name ? "Lead saved" : "Lead added",
});

const values = () => ({
	...form,
	name: props.name,
	visit_on: form.visit_on ? form.visit_on.replace("T", " ") + ":00" : null,
});

async function save() {
	await run(values());
	emit("close");
}

const recording = ref(false);
async function recordToken() {
	recording.value = true;
	try {
		await post("save_lead", { data: values() });
		await post("record_lead_token", { name: props.name, ...token });
		toast("Token recorded. The bed is held.");
		bumpData();
		await load();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		recording.value = false;
	}
}

function whatsapp(
	text = `Hello ${lead.value?.lead_name}, this is about your enquiry at ${lead.value?.property}.`
) {
	const digits = (lead.value?.mobile_no || "").replace(/[^\d]/g, "");
	const number = digits.length === 10 ? `91${digits}` : digits;
	return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

const asking = ref(false);
async function askForToken() {
	asking.value = true;
	try {
		await post("save_lead", { data: values() });
		const link = await post("ask_lead_for_token", { name: props.name, amount: token.amount });
		window.open(
			whatsapp(
				`Hello ${lead.value.lead_name}, you can hold your bed at ${lead.value.property} by paying the token here: ${link}`
			),
			"_blank"
		);
		await load();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		asking.value = false;
	}
}
</script>
