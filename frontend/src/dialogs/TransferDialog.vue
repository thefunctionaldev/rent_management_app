<template>
	<Modal
		open
		title="Move to another bed"
		:subtitle="tenantName"
		width="md"
		@close="$emit('close')"
	>
		<div v-if="!data" class="space-y-2">
			<Skeleton class="h-10" /><Skeleton class="h-32" />
		</div>

		<div v-else-if="result" class="space-y-4 text-sm">
			<div class="flex items-center gap-3">
				<span
					class="grid size-11 place-items-center rounded-full bg-emerald-50 text-emerald-600"
					><CircleCheck class="size-6"
				/></span>
				<div>
					<p class="text-base font-semibold">
						Moved to room {{ chosenRoom?.room_number }}, bed {{ result.bed_no }}
					</p>
					<p class="text-slate-500">
						{{ money(result.rent) }} a month · deposit {{ money(result.deposit) }}
					</p>
				</div>
			</div>
			<ul class="space-y-1 text-slate-600">
				<li>Room {{ data.stay.room_number }} ended the night before the move.</li>
				<li v-if="result.bill">
					This month's bill for the new room:
					<RouterLink
						:to="`/invoices?invoice=${result.bill}`"
						class="text-brand-600"
						@click="$emit('close')"
						>{{ result.bill }}</RouterLink
					>
				</li>
				<li v-else>
					Both rooms are billed for their nights when this month's bills are made.
				</li>
				<li v-if="result.top_up">
					{{ money(result.top_up) }} deposit top-up is on that bill.
				</li>
				<li v-if="result.refund_later">
					{{ money(result.refund_later) }} of the deposit is refunded when they move out.
				</li>
			</ul>
			<div v-if="result.signing" class="flex gap-2">
				<Button variant="primary" class="flex-1" :icon="MessageCircle" @click="whatsapp"
					>Send agreement to sign</Button
				>
				<Button :icon="Copy" @click="copy">Copy link</Button>
			</div>
		</div>

		<form v-else id="transfer-form" class="space-y-4" @submit.prevent="save">
			<p class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
				Now in room {{ data.stay.room_number }} · {{ money(data.stay.rent) }} a month ·
				deposit {{ money(data.stay.deposit)
				}}{{ data.stay.deposit_collected ? "" : " (not collected)" }}
			</p>
			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="New room" required>
					<select v-model="form.room" class="input" required @change="pickRoom">
						<option value="" disabled>Choose a room…</option>
						<optgroup
							v-for="(rooms, building) in byBuilding"
							:key="building"
							:label="building"
						>
							<option v-for="r in rooms" :key="r.name" :value="r.name">
								{{ r.room_number }} · {{ money(r.room_rent) }} ·
								{{ r.free_beds.length }} free
							</option>
						</optgroup>
					</select>
				</Field>
				<Field label="Bed" required>
					<select
						v-model.number="form.bed_no"
						class="input"
						:disabled="!chosenRoom"
						required
					>
						<option v-for="b in chosenRoom?.free_beds || []" :key="b" :value="b">
							Bed {{ b }}
						</option>
					</select>
				</Field>
				<Field label="Moving on" required>
					<input
						v-model="form.transfer_date"
						type="date"
						class="input"
						:min="minDate"
						:max="data.today"
						required
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
				<Field label="Deposit for the new room">
					<input
						v-model.number="form.new_deposit"
						type="number"
						min="0"
						class="input tabular"
					/>
				</Field>
			</div>
			<p v-if="depositNote" class="text-xs text-slate-500">{{ depositNote }}</p>
			<p class="text-xs text-slate-500">
				Each room is billed for the nights spent in it. The agreement, notice, lock-in and
				police verification (in the same building) go with them.
			</p>
			<label class="flex items-start gap-2 text-sm text-slate-700">
				<input
					v-model="form.send_for_signing"
					type="checkbox"
					class="mt-0.5 size-4 accent-brand-600"
				/>
				<span
					>Send the updated agreement to sign
					<span class="block text-xs text-slate-500"
						>With the new room and rent</span
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
					form="transfer-form"
					:loading="saving"
					:icon="ArrowRightLeft"
					>Move</Button
				>
			</template>
			<Button v-else-if="result" variant="primary" @click="$emit('close')">Done</Button>
		</template>
	</Modal>
</template>

<script setup>
import { ArrowRightLeft, CircleCheck, Copy, MessageCircle } from "lucide-vue-next";
import { computed, reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import { bumpData, toast } from "@/store";
import { money } from "@/utils";

const props = defineProps({
	allotment: { type: String, required: true },
	tenantName: { type: String, default: "" },
	firstName: { type: String, default: "" },
});
defineEmits(["close"]);

const data = ref(null);
const result = ref(null);
const saving = ref(false);
const form = reactive({
	room: "",
	bed_no: null,
	transfer_date: "",
	new_rent: null,
	new_deposit: null,
	send_for_signing: true,
});

get("get_transfer_options", { allotment: props.allotment })
	.then((d) => {
		data.value = d;
		form.transfer_date = d.today;
	})
	.catch((e) => toast(e.message, "error"));

const byBuilding = computed(() => {
	const groups = {};
	for (const r of data.value?.rooms || []) {
		if (r.name === data.value.stay.room && r.free_beds.length === 0) continue;
		(groups[r.property] ||= []).push(r);
	}
	return groups;
});
const chosenRoom = computed(() => data.value?.rooms.find((r) => r.name === form.room));
function pickRoom() {
	const r = chosenRoom.value;
	form.bed_no = r?.free_beds[0] || null;
	form.new_rent = r?.room_rent || data.value.stay.rent;
	form.new_deposit = r?.deposit || data.value.stay.deposit;
}
const minDate = computed(() => {
	const d = new Date(`${data.value.stay.since}T00:00:00`);
	d.setDate(d.getDate() + 1);
	return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
});
const depositNote = computed(() => {
	if (!data.value?.stay.deposit_collected || form.new_deposit === null) return "";
	const diff = form.new_deposit - data.value.stay.deposit;
	if (diff > 0) return `${money(diff)} more deposit is added to the new room's first bill.`;
	if (diff < 0) return `${money(-diff)} of the deposit is refunded when they move out.`;
	return "The deposit stays as it is.";
});

async function save() {
	saving.value = true;
	try {
		result.value = await post("transfer_stay", {
			allotment: props.allotment,
			...form,
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
	const text = `Hello ${
		props.firstName || props.tenantName
	}, your rental agreement is updated for your new room. Please read and sign it here: ${
		result.value.signing.url
	}`;
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
