<template>
	<Modal
		open
		width="lg"
		:title="`${type} checklist`"
		:subtitle="`${allotment.tenant_name} · Room ${allotment.room}`"
		@close="$emit('close')"
	>
		<div v-if="!doc" class="space-y-3">
			<Skeleton v-for="i in 5" :key="i" class="h-12" />
		</div>
		<div v-else class="space-y-4">
			<p v-if="doc.locked" class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
				{{
					type === "Move-in"
						? "The tenant signed their agreement with this checklist, so it can't change."
						: "The deposit is settled with this checklist, so it can't change."
				}}
			</p>
			<p
				v-else-if="type === 'Move-out' && !doc.move_in_done"
				class="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
			>
				There is no move-in checklist for this stay, so there's nothing to compare with.
			</p>
			<p
				v-else-if="!doc.items.length"
				class="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
			>
				This room has no items yet. Add them here, or edit the room to keep them for next
				time.
			</p>

			<div class="flex flex-wrap gap-4">
				<Field label="Date">
					<input
						v-model="doc.inspection_date"
						class="input"
						type="date"
						:disabled="doc.locked"
					/>
				</Field>
				<div class="flex items-end gap-1.5 text-xs">
					<button
						v-if="!doc.locked"
						type="button"
						class="rounded-full bg-slate-100 px-3 py-1.5 font-medium text-slate-600 hover:bg-emerald-50 hover:text-emerald-700"
						@click="doc.items.forEach((r) => (r.condition = 'Good'))"
					>
						All good
					</button>
				</div>
			</div>

			<ul class="divide-y divide-slate-100 rounded-xl border border-slate-200">
				<li v-for="(row, i) in doc.items" :key="i" class="space-y-2 p-3">
					<div class="flex flex-wrap items-center gap-2">
						<input
							v-model="row.item"
							class="input w-40 flex-1 font-medium"
							:disabled="doc.locked"
						/>
						<input
							v-model.number="row.quantity"
							class="input tabular w-16"
							type="number"
							min="1"
							title="Quantity"
							:disabled="doc.locked"
						/>
						<div class="flex overflow-hidden rounded-lg ring-1 ring-slate-200">
							<button
								v-for="c in conditions"
								:key="c"
								type="button"
								class="px-2.5 py-1.5 text-xs font-medium transition"
								:class="
									row.condition === c
										? toneOn[c]
										: 'bg-white text-slate-500 hover:bg-slate-50'
								"
								:disabled="doc.locked"
								@click="setCondition(row, c)"
							>
								{{ c }}
							</button>
						</div>
						<label
							class="relative grid size-9 cursor-pointer place-items-center overflow-hidden rounded-lg ring-1 ring-slate-200 hover:bg-slate-50"
							:title="row.photo || row.photo_upload ? 'Change photo' : 'Add photo'"
						>
							<img
								v-if="row.photo_upload || row.photo"
								:src="row.photo_upload || row.photo"
								alt=""
								class="size-full object-cover"
							/>
							<Camera v-else class="size-4 text-slate-400" />
							<input
								type="file"
								accept="image/*"
								class="sr-only"
								:disabled="doc.locked"
								@change="(e) => addPhoto(row, e)"
							/>
						</label>
					</div>
					<div class="flex flex-wrap items-center gap-2 text-xs">
						<span v-if="row.move_in_condition" class="text-slate-500"
							>At move-in: <b>{{ row.move_in_condition }}</b></span
						>
						<input
							v-model="row.notes"
							class="input flex-1 py-1 text-xs"
							placeholder="Notes"
							:disabled="doc.locked"
						/>
						<template v-if="charged(row)">
							<span class="text-slate-500">Charge</span>
							<input
								v-model.number="row.charge"
								class="input tabular w-24 py-1 text-xs"
								type="number"
								min="0"
								:disabled="doc.locked"
							/>
						</template>
					</div>
				</li>
			</ul>
			<button
				v-if="!doc.locked"
				type="button"
				class="text-sm font-medium text-brand-600 hover:underline"
				@click="doc.items.push({ item: '', quantity: 1, condition: 'Good', charge: 0 })"
			>
				+ Add item
			</button>

			<Field label="Notes">
				<textarea v-model="doc.notes" class="input" rows="2" :disabled="doc.locked" />
			</Field>
			<p v-if="type === 'Move-out'" class="text-sm">
				Charges: <b class="tabular">{{ money(total) }}</b>
				<span class="text-slate-500">
					· offered as deductions when you settle the deposit</span
				>
			</p>
		</div>
		<template #footer>
			<Button @click="$emit('close')">{{ doc?.locked ? "Close" : "Cancel" }}</Button>
			<template v-if="doc && !doc.locked">
				<Button :loading="saving === 'draft'" @click="save(false)">Save draft</Button>
				<Button variant="primary" :loading="saving === 'done'" @click="save(true)">{{
					doc.status === "Completed" ? "Save" : "Complete checklist"
				}}</Button>
			</template>
		</template>
	</Modal>
</template>

<script setup>
import { Camera } from "lucide-vue-next";
import { computed, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import Skeleton from "@/components/Skeleton.vue";
import { bumpData, toast } from "@/store";
import { money, shrinkImage } from "@/utils";

const props = defineProps({
	allotment: { type: Object, required: true },
	type: { type: String, required: true }, // Move-in or Move-out
});
const emit = defineEmits(["close"]);

const conditions = ["Good", "Fair", "Damaged", "Missing"];
const toneOn = {
	Good: "bg-emerald-600 text-white",
	Fair: "bg-sky-600 text-white",
	Damaged: "bg-amber-500 text-white",
	Missing: "bg-rose-600 text-white",
};

const doc = ref(null);
get("get_room_inspection", { allotment: props.allotment.name, inspection_type: props.type }).then(
	(data) => (doc.value = data)
);

const charged = (row) =>
	props.type === "Move-out" && ["Damaged", "Missing"].includes(row.condition);
const total = computed(() =>
	(doc.value?.items || []).reduce((sum, r) => sum + (charged(r) ? Number(r.charge) || 0 : 0), 0)
);

function setCondition(row, condition) {
	row.condition = condition;
	// a missing item costs what it takes to replace it
	if (condition === "Missing" && !Number(row.charge))
		row.charge = (Number(row.replacement_cost) || 0) * (row.quantity || 1);
	if (!charged(row)) row.charge = 0;
}

async function addPhoto(row, event) {
	const file = event.target.files?.[0];
	event.target.value = "";
	if (!file) return;
	try {
		row.photo_upload = await shrinkImage(file, 1280);
	} catch {
		toast("That picture could not be read", "error");
	}
}

const saving = ref(null);
async function save(complete) {
	saving.value = complete ? "done" : "draft";
	try {
		await post("save_room_inspection", { data: { ...doc.value, complete: complete ? 1 : 0 } });
		toast(complete ? `${props.type} checklist done` : "Checklist saved");
		bumpData();
		emit("close");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = null;
	}
}
</script>
