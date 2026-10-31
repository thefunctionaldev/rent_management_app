<template>
	<Modal
		open
		title="Renew agreement"
		:subtitle="allotment.tenant_name"
		width="sm"
		@close="$emit('close')"
	>
		<div v-if="!data" class="space-y-2">
			<Skeleton class="h-10" /><Skeleton class="h-24" />
		</div>

		<div v-else-if="result" class="space-y-4 text-sm">
			<div class="flex items-center gap-3">
				<span
					class="grid size-11 place-items-center rounded-full bg-emerald-50 text-emerald-600"
					><CircleCheck class="size-6"
				/></span>
				<div>
					<p class="text-base font-semibold">Renewed until {{ date(result.end) }}</p>
					<p class="text-slate-500">
						From {{ date(result.start) }} · {{ money(result.rent) }} a month
					</p>
				</div>
			</div>
			<template v-if="result.signing">
				<p class="text-slate-500">
					The tenant has been told in their app. Send them the link to read and sign it:
				</p>
				<div class="flex gap-2">
					<Button
						variant="primary"
						class="flex-1"
						:icon="MessageCircle"
						@click="whatsapp"
						>Send on WhatsApp</Button
					>
					<Button :icon="Copy" @click="copy">Copy link</Button>
				</div>
			</template>
		</div>

		<form v-else id="renew-form" class="space-y-4" @submit.prevent="save">
			<p class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
				Current agreement: {{ date(data.current_start) }} to
				{{ data.current_end ? date(data.current_end) : "no end date"
				}}<template v-if="data.renewals">
					· renewed {{ data.renewals }} time{{
						data.renewals === 1 ? "" : "s"
					}}</template
				>
			</p>
			<div class="grid grid-cols-2 gap-4">
				<Field label="Renew for (months)" required>
					<input
						v-model.number="form.months"
						type="number"
						min="1"
						max="60"
						class="input tabular"
						required
						@change="load"
					/>
				</Field>
				<Field label="Rent from then" required>
					<input
						v-model.number="form.new_rent"
						type="number"
						min="1"
						class="input tabular"
						required
					/>
				</Field>
			</div>
			<p class="text-sm">
				New term: <b>{{ date(data.start) }}</b> to <b>{{ date(data.end) }}</b>
			</p>
			<p
				v-if="data.increase_percent && form.new_rent === data.suggested_rent"
				class="text-xs text-slate-500"
			>
				That's the agreed {{ data.increase_percent }}% increase on {{ money(data.rent) }}.
			</p>
			<label class="flex items-start gap-2 text-sm text-slate-700">
				<input
					v-model="form.send_for_signing"
					type="checkbox"
					class="mt-0.5 size-4 accent-brand-600"
				/>
				<span
					>Send it to the tenant to sign
					<span class="block text-xs text-slate-500"
						>They read the renewed agreement and sign it with a code, like at
						check-in</span
					></span
				>
			</label>
		</form>

		<template #footer>
			<template v-if="data && !result">
				<Button @click="$emit('close')">Cancel</Button>
				<Button
					variant="primary"
					type="submit"
					form="renew-form"
					:loading="saving"
					:icon="RefreshCw"
					>Renew</Button
				>
			</template>
			<Button v-else-if="result" variant="primary" @click="$emit('close')">Done</Button>
		</template>
	</Modal>
</template>

<script setup>
import { CircleCheck, Copy, MessageCircle, RefreshCw } from "lucide-vue-next";
import { reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import { bumpData, toast } from "@/store";
import { date, money } from "@/utils";

// allotment: { name, tenant_name, first_name? }
const props = defineProps({ allotment: { type: Object, required: true } });
defineEmits(["close"]);

const data = ref(null);
const form = reactive({ months: null, new_rent: null, send_for_signing: true });
const result = ref(null);
const saving = ref(false);

async function load() {
	try {
		data.value = await get("get_renewal", {
			allotment: props.allotment.name,
			months: form.months,
		});
		form.months = data.value.months;
		if (form.new_rent === null) form.new_rent = data.value.suggested_rent;
	} catch (e) {
		toast(e.message, "error");
	}
}
load();

async function save() {
	saving.value = true;
	try {
		result.value = await post("renew_agreement", {
			allotment: props.allotment.name,
			months: form.months,
			new_rent: form.new_rent,
			send_for_signing: form.send_for_signing ? 1 : 0,
		});
		bumpData();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}

function whatsapp() {
	const digits = (result.value.signing.mobile_no || "").replace(/[^\d]/g, "");
	const name = props.allotment.first_name || props.allotment.tenant_name;
	const text = `Hello ${name}, your rental agreement is renewed until ${date(
		result.value.end
	)}. Please read and sign it here: ${result.value.signing.url}`;
	window.open(
		`https://wa.me/${digits.length === 10 ? `91${digits}` : digits}?text=${encodeURIComponent(
			text
		)}`,
		"_blank"
	);
}
async function copy() {
	await navigator.clipboard?.writeText(result.value.signing.url);
	toast("Link copied");
}
</script>
