<template>
	<Modal
		open
		:title="notice?.name ? 'Edit notice' : 'New notice'"
		subtitle="Shown in the tenant app and on their phones"
		width="lg"
		@close="$emit('close')"
	>
		<form id="announcement-form" class="space-y-4" @submit.prevent="save(true)">
			<div v-if="!notice?.name" class="flex flex-wrap gap-1.5">
				<button
					v-for="t in templates"
					:key="t.title"
					type="button"
					class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-brand-50 hover:text-brand-700"
					@click="useTemplate(t)"
				>
					{{ t.label }}
				</button>
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="For">
					<select v-model="form.property" class="input">
						<option value="">All buildings</option>
						<option v-for="b in buildings" :key="b.name" :value="b.name">
							{{ b.name }}
						</option>
					</select>
				</Field>
				<Field label="Category">
					<select v-model="form.category" class="input">
						<option v-for="c in categories" :key="c">{{ c }}</option>
					</select>
				</Field>
			</div>
			<Field label="Title" required>
				<input v-model="form.title" class="input" maxlength="140" required />
			</Field>
			<Field label="Message" required>
				<textarea v-model="form.message" class="input" rows="5" required />
			</Field>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Show until" hint="empty: until you take it down">
					<input v-model="form.expires_on" type="date" class="input" :min="boot.today" />
				</Field>
				<label class="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
					<input v-model="form.pinned" type="checkbox" class="size-4 accent-brand-600" />
					Pin to the top
				</label>
			</div>
			<label
				class="flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"
			>
				<input
					v-model="form.send_whatsapp"
					type="checkbox"
					class="mt-0.5 size-4 accent-brand-600"
				/>
				<span>
					Also send it on WhatsApp and by email
					<span class="block text-xs text-slate-500"
						>For things everyone must see. WhatsApp charges for each message.</span
					>
				</span>
			</label>
		</form>
		<template #footer>
			<Button :loading="saving === 'draft'" @click="save(false)">Save draft</Button>
			<Button
				variant="primary"
				type="submit"
				form="announcement-form"
				:icon="Megaphone"
				:loading="saving === 'publish'"
				>Publish</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { Megaphone } from "lucide-vue-next";
import { reactive, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { activeProperties, boot, bumpData, toast, ui } from "@/store";

const props = defineProps({ notice: { type: Object, default: null } });
const emit = defineEmits(["close"]);

const categories = [
	"General",
	"Water",
	"Electricity",
	"Maintenance",
	"Food",
	"Rules",
	"Event",
	"Urgent",
];
const buildings = activeProperties();
const n = props.notice || {};
const form = reactive({
	name: n.name,
	title: n.title || "",
	message: n.message || "",
	category: n.category || "General",
	property: n.property || ui.property || "",
	pinned: !!n.pinned,
	expires_on: n.expires_on || "",
	send_whatsapp: !!n.send_whatsapp,
});

const tomorrow = (() => {
	const d = new Date(`${boot.today}T00:00:00`);
	d.setDate(d.getDate() + 1);
	return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
})();
const templates = [
	{
		label: "Water cut",
		category: "Water",
		title: `No water on ${tomorrow}`,
		message:
			"The water supply will be off from 10 am to 2 pm for tank cleaning. Please store some water beforehand.",
	},
	{
		label: "Power cut",
		category: "Electricity",
		title: `Power cut on ${tomorrow}`,
		message:
			"BESCOM has a scheduled power cut from 10 am to 4 pm. The backup will run the lights and Wi-Fi only.",
	},
	{
		label: "Pest control",
		category: "Maintenance",
		title: "Pest control this Sunday",
		message:
			"Pest control is on Sunday from 11 am. Please keep food covered and stay out of your room for 2 hours after it's done.",
	},
	{
		label: "Repair visit",
		category: "Maintenance",
		title: "Plumber visiting tomorrow",
		message:
			"A plumber will check all bathrooms tomorrow between 10 am and 1 pm. Please keep your bathroom accessible.",
	},
	{
		label: "Rent reminder",
		category: "General",
		title: "Rent is due on the 5th",
		message:
			"A reminder that this month's rent is due on the 5th. You can pay in the app by UPI. Thank you!",
	},
	{
		label: "Festival",
		category: "Event",
		title: "Diwali dinner on Saturday",
		message:
			"Join us for a special Diwali dinner on Saturday at 8 pm in the dining hall. Sweets on us!",
	},
	{
		label: "House rule",
		category: "Rules",
		title: "A reminder about visitors",
		message:
			"Visitors are allowed until 9 pm and must sign in at the gate. Overnight guests need the warden's OK.",
	},
];
function useTemplate(t) {
	Object.assign(form, { title: t.title, message: t.message, category: t.category });
}

const saving = ref(null);
async function save(publish) {
	if (!form.title.trim() || !form.message.trim())
		return toast("Write a title and a message", "error");
	saving.value = publish ? "publish" : "draft";
	try {
		await post("save_notice", {
			data: {
				...form,
				pinned: form.pinned ? 1 : 0,
				send_whatsapp: form.send_whatsapp ? 1 : 0,
			},
			publish: publish ? 1 : 0,
		});
		toast(publish ? "Published to your tenants" : "Draft saved");
		bumpData();
		emit("close");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = null;
	}
}
</script>
