<template>
	<Modal
		open
		title="Settle security deposit"
		:subtitle="`${allotment.tenant_name} · Room ${allotment.room}`"
		width="lg"
		@close="$emit('close')"
	>
		<form id="settle-form" class="grid gap-6 md:grid-cols-[1fr_15rem]" @submit.prevent="save">
			<div class="space-y-5">
				<div>
					<div class="mb-2 flex items-center justify-between">
						<span class="label mb-0">Deductions</span>
						<button
							type="button"
							class="text-xs font-medium text-brand-600 hover:underline"
							@click="addDeduction"
						>
							+ Add deduction
						</button>
					</div>
					<div v-if="deductions.length" class="space-y-2">
						<div
							v-for="(row, i) in deductions"
							:key="i"
							class="grid grid-cols-[8rem_1fr_6rem_auto] gap-2"
						>
							<select v-model="row.reason" class="input">
								<option v-for="r in reasons" :key="r">{{ r }}</option>
							</select>
							<input v-model="row.description" class="input" placeholder="Details" />
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
								@click="deductions.splice(i, 1)"
							>
								<Trash2 class="size-4" />
							</button>
						</div>
					</div>
					<p
						v-else
						class="rounded-xl border border-dashed border-slate-200 py-4 text-center text-sm text-slate-400"
					>
						No deductions — damages, cleaning, repairs…
					</p>
					<p
						v-if="checklist?.status === 'Completed'"
						class="mt-2 text-xs text-slate-500"
					>
						Damages from the move-out checklist are filled in.
					</p>
					<p v-else class="mt-2 text-xs text-amber-700">
						{{
							checklist
								? "The move-out checklist isn't completed yet."
								: "No move-out checklist yet. Do one from the tenant's profile to charge damages."
						}}
					</p>
				</div>

				<label class="flex items-start gap-2 text-sm text-slate-700">
					<input
						v-model="adjustRent"
						type="checkbox"
						class="mt-0.5 size-4 accent-brand-600"
					/>
					<span
						>Use the deposit to pay off unpaid rent
						<span class="block text-xs text-slate-500"
							>Posted as payments against the oldest invoices first</span
						></span
					>
				</label>

				<div v-if="preview?.refund_amount > 0" class="grid gap-4 sm:grid-cols-2">
					<Field label="Refund mode" required>
						<select v-model="form.mode_of_refund" class="input" required>
							<option v-for="m in refundModes" :key="m">{{ m }}</option>
						</select>
					</Field>
					<Field label="Reference number"
						><input v-model="form.reference_no" class="input"
					/></Field>
				</div>
				<Field label="Remarks"><input v-model="form.remarks" class="input" /></Field>
			</div>

			<!-- live breakdown -->
			<div class="h-fit rounded-2xl bg-slate-900 p-5 text-white">
				<p class="text-xs font-medium tracking-wide text-slate-400 uppercase">
					Settlement
				</p>
				<dl class="tabular mt-4 space-y-2.5 text-sm" :class="previewing && 'opacity-60'">
					<div class="flex justify-between">
						<dt class="text-slate-400">Deposit</dt>
						<dd>
							{{ money(preview?.security_deposit ?? allotment.security_deposit) }}
						</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-slate-400">Deductions</dt>
						<dd>− {{ money(preview?.total_deductions) }}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-slate-400">Rent adjusted</dt>
						<dd>− {{ money(preview?.rent_adjusted) }}</dd>
					</div>
					<div v-if="preview?.outstanding_rent" class="flex justify-between text-xs">
						<dt class="text-slate-500">Unpaid rent</dt>
						<dd class="text-slate-400">{{ money(preview.outstanding_rent) }}</dd>
					</div>
				</dl>
				<div class="mt-4 border-t border-white/10 pt-4">
					<template v-if="preview?.balance_payable_by_tenant > 0">
						<p class="text-xs text-rose-300">Tenant still owes</p>
						<p class="tabular text-2xl font-semibold text-rose-300">
							{{ money(preview.balance_payable_by_tenant) }}
						</p>
					</template>
					<template v-else>
						<p class="text-xs text-emerald-300">Refund to tenant</p>
						<p class="tabular text-2xl font-semibold text-emerald-300">
							{{ money(preview?.refund_amount) }}
						</p>
					</template>
				</div>
			</div>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button
				variant="primary"
				type="submit"
				form="settle-form"
				:loading="loading"
				:disabled="!preview"
				:icon="ShieldCheck"
				>Settle deposit</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { ShieldCheck, Trash2 } from "lucide-vue-next";
import { reactive, ref, watch } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { toast } from "@/store";
import { useAction } from "@/useResource";
import { debounce, money } from "@/utils";

const props = defineProps({ allotment: { type: Object, required: true } });
const emit = defineEmits(["close"]);

const reasons = ["Damages", "Cleaning", "Repairs", "Unpaid Utilities", "Lost Keys", "Other"];
const refundModes = ["Bank Transfer", "UPI", "Cash", "Cheque", "Other"];
const deductions = reactive([]);
const adjustRent = ref(true);
const form = reactive({ mode_of_refund: "Bank Transfer", reference_no: "", remarks: "" });
const preview = ref(null);
const previewing = ref(false);

// the move-out checklist's charges, ready to keep or change
const checklist = ref(null);
get("get_checklist_deductions", { allotment: props.allotment.name }).then((data) => {
	checklist.value = data.move_out;
	if (!deductions.length) deductions.push(...data.deductions);
});

function addDeduction() {
	deductions.push({ reason: "Cleaning", description: "", amount: "" });
}

const args = () => ({
	allotment: props.allotment.name,
	deductions: deductions.filter((d) => Number(d.amount) > 0),
	adjust_outstanding_rent: adjustRent.value ? 1 : 0,
});

const refreshPreview = debounce(async () => {
	previewing.value = true;
	try {
		preview.value = await post("preview_settlement", args());
	} catch (e) {
		toast(e.message, "error");
	} finally {
		previewing.value = false;
	}
}, 350);
watch([deductions, adjustRent], refreshPreview, { deep: true, immediate: true });

const { loading, run } = useAction(() => post("settle_deposit", { ...args(), ...form }), {
	success: "Deposit settled",
});

async function save() {
	await run();
	emit("close");
}
</script>
