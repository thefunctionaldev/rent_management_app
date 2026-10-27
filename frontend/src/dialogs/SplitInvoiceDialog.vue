<template>
	<Modal
		open
		title="Pay in instalments"
		:subtitle="`${invoice.tenant_name} · ${invoice.billing_month} ${invoice.billing_year}`"
		@close="$emit('close')"
	>
		<form id="split-form" class="space-y-4" @submit.prevent="save">
			<p class="text-sm text-slate-600">
				Split the {{ money(total) }} invoice into parts with their own due dates. What's
				already paid ({{ money(invoice.paid_amount) }}) counts towards the first ones.
				Reminders and late fees follow the next unpaid part.
			</p>
			<div class="flex flex-wrap gap-2">
				<button
					v-for="n in [2, 3, 4]"
					:key="n"
					type="button"
					class="rounded-full px-3 py-1 text-xs font-medium ring-1"
					:class="
						rows.length === n
							? 'bg-brand-600 text-white ring-brand-600'
							: 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
					"
					@click="evenly(n)"
				>
					{{ n }} parts
				</button>
			</div>
			<div
				v-for="(row, i) in rows"
				:key="i"
				class="grid grid-cols-[1.5rem_1fr_1fr_auto] items-center gap-2"
			>
				<span class="tabular text-sm text-slate-400">{{ i + 1 }}</span>
				<input
					v-model="row.due_date"
					type="date"
					class="input"
					:min="invoice.posting_date"
					required
				/>
				<input
					v-model.number="row.amount"
					type="number"
					min="1"
					step="0.01"
					class="input tabular"
					required
				/>
				<button
					type="button"
					class="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-rose-600 disabled:opacity-30"
					:disabled="rows.length <= 2"
					title="Remove"
					@click="rows.splice(i, 1)"
				>
					<Trash2 class="size-4" />
				</button>
			</div>
			<button
				type="button"
				class="text-sm font-medium text-brand-600 hover:underline"
				@click="rows.push({ due_date: nextDate(rows.at(-1).due_date), amount: 0 })"
			>
				+ Add a part
			</button>
			<p class="text-sm" :class="off ? 'text-rose-600' : 'text-slate-500'">
				Adds up to {{ money(sum)
				}}<template v-if="off">
					· {{ money(Math.abs(off)) }} {{ off > 0 ? "too much" : "short" }}</template
				>
			</p>
		</form>
		<template #footer>
			<Button
				v-if="instalments.length"
				variant="ghost"
				class="sm:mr-auto"
				:loading="removing"
				@click="remove"
				>Back to one due date</Button
			>
			<Button @click="$emit('close')">Cancel</Button>
			<Button
				variant="primary"
				type="submit"
				form="split-form"
				:loading="loading"
				:disabled="!!off"
				>Save instalments</Button
			>
		</template>
	</Modal>
</template>

<script setup>
import { Trash2 } from "lucide-vue-next";
import { computed, ref } from "vue";

import { post } from "@/api";
import Button from "@/components/Button.vue";
import Modal from "@/components/Modal.vue";
import { boot, bumpData, toast } from "@/store";
import { useAction } from "@/useResource";
import { money } from "@/utils";

const props = defineProps({
	invoice: { type: Object, required: true },
	instalments: { type: Array, default: () => [] },
});
const emit = defineEmits(["close"]);

// everything but the early payment discount, which split invoices don't get
const total =
	Math.round(((props.invoice.final_amount || 0) + (props.invoice.early_discount || 0)) * 100) /
	100;

function nextDate(value, days = 15) {
	const d = new Date(`${value}T00:00:00`);
	d.setDate(d.getDate() + days);
	return d.toLocaleDateString("en-CA");
}

const rows = ref(
	props.instalments.length
		? props.instalments.map((r) => ({ due_date: r.due_date, amount: r.amount }))
		: []
);
function evenly(n) {
	// from the due date, or today if that has passed
	const due = props.invoice.next_due_date || props.invoice.due_date;
	const start = due > boot.today ? due : boot.today;
	const part = Math.floor(total / n);
	rows.value = Array.from({ length: n }, (_, i) => ({
		due_date: nextDate(start, i * 15),
		amount: i === n - 1 ? Math.round((total - part * (n - 1)) * 100) / 100 : part,
	}));
}
if (!rows.value.length) evenly(2);

const sum = computed(() => rows.value.reduce((s, r) => s + (Number(r.amount) || 0), 0));
const off = computed(() => Math.round((sum.value - total) * 100) / 100);

const { loading, run } = useAction(
	() => post("split_invoice", { name: props.invoice.name, instalments: rows.value }),
	{ success: "Instalments saved" }
);
async function save() {
	await run();
	emit("close");
}

const removing = ref(false);
async function remove() {
	removing.value = true;
	try {
		await post("split_invoice", { name: props.invoice.name, instalments: [] });
		toast("Back to one due date");
		bumpData();
		emit("close");
	} catch (e) {
		toast(e.message, "error");
	} finally {
		removing.value = false;
	}
}
</script>
