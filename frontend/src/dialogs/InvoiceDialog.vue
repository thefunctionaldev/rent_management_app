<template>
	<Modal
		open
		title="New rent invoice"
		subtitle="Rent is pro-rated for the days the tenant stayed"
		width="lg"
		@close="$emit('close')"
	>
		<form id="invoice-form" class="space-y-5" @submit.prevent="save">
			<Field label="Tenant / room" required>
				<select v-model="form.tenant_space_allotment" class="input" required>
					<option value="" disabled>Select an allotment</option>
					<option v-for="a in allotments.data.value" :key="a.name" :value="a.name">
						{{ a.tenant_name }} · Room {{ a.room }} · {{ money(a.rent_amount) }}/mo{{
							a.status === "Vacated" ? " · moved out" : ""
						}}
					</option>
				</select>
			</Field>
			<div class="grid gap-4 sm:grid-cols-3">
				<Field label="Month" required>
					<select v-model="form.billing_month" class="input" required>
						<option v-for="m in boot.months" :key="m">{{ m }}</option>
					</select>
				</Field>
				<Field label="Year" required>
					<input
						v-model="form.billing_year"
						type="number"
						class="input tabular"
						required
					/>
				</Field>
				<Field label="Due date" hint="Optional; defaults from settings">
					<input v-model="form.due_date" type="date" class="input" />
				</Field>
			</div>

			<div>
				<div class="mb-2 flex items-center justify-between">
					<span class="label mb-0">Additional charges</span>
					<button
						type="button"
						class="text-xs font-medium text-brand-600 hover:underline"
						@click="addCharge"
					>
						+ Add charge
					</button>
				</div>
				<div v-if="form.charges.length" class="space-y-2">
					<div
						v-for="(row, i) in form.charges"
						:key="i"
						class="grid grid-cols-[8.5rem_1fr_7rem_auto] gap-2"
					>
						<select v-model="row.charge_type" class="input">
							<option v-for="c in chargeTypes" :key="c">{{ c }}</option>
						</select>
						<input
							v-model="row.description"
							class="input"
							placeholder="Description (e.g. meter reading)"
						/>
						<input
							v-model="row.amount"
							type="number"
							min="0"
							class="input tabular"
							placeholder="0"
						/>
						<button
							type="button"
							class="rounded-lg px-2 text-slate-400 hover:bg-slate-100 hover:text-rose-600"
							@click="form.charges.splice(i, 1)"
						>
							<Trash2 class="size-4" />
						</button>
					</div>
				</div>
				<p
					v-else
					class="rounded-xl border border-dashed border-slate-200 py-4 text-center text-sm text-slate-400"
				>
					No extra charges — electricity, water, maintenance…
				</p>
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<Field label="Discount">
					<input
						v-model="form.discount_amount"
						type="number"
						min="0"
						class="input tabular"
						placeholder="0"
					/>
				</Field>
				<Field label="Remarks"><input v-model="form.remarks" class="input" /></Field>
			</div>
			<label class="flex items-center gap-2 text-sm text-slate-700">
				<input v-model="form.submit" type="checkbox" class="size-4 accent-brand-600" />
				Submit now (otherwise saved as a draft for review)
			</label>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="invoice-form" :loading="loading"
				>Create invoice</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { Trash2 } from "lucide-vue-next";
import { reactive } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { boot, scope } from "@/store";
import { useAction, useResource } from "@/useResource";
import { currentMonth, money } from "@/utils";

const props = defineProps({ allotment: { type: String, default: "" } });
const emit = defineEmits(["close", "created"]);

const chargeTypes = ["Electricity", "Water", "Maintenance", "Parking", "Late Fee", "Other"];
const { month, year } = currentMonth();
const form = reactive({
	tenant_space_allotment: props.allotment,
	billing_month: month,
	billing_year: year,
	due_date: "",
	charges: [],
	discount_amount: "",
	remarks: "",
	submit: true,
});
const allotments = useResource(() => get("get_billable_allotments", scope()), { initial: [] });

function addCharge() {
	form.charges.push({ charge_type: "Electricity", description: "", amount: "" });
}

const { loading, run } = useAction(
	() =>
		post("create_invoice", {
			...form,
			discount_amount: form.discount_amount || 0,
			submit: form.submit ? 1 : 0,
		}),
	{ success: (name) => `Invoice ${name} created` }
);

async function save() {
	await run();
	emit("close");
}
</script>
