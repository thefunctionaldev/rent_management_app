<template>
	<div class="space-y-2">
		<div
			v-for="(row, i) in items"
			:key="i"
			class="grid grid-cols-[1fr_4rem_6.5rem_auto] items-center gap-2"
		>
			<input v-model="row.item" class="input" placeholder="Item" />
			<input
				v-model.number="row.quantity"
				class="input tabular"
				type="number"
				min="1"
				title="Quantity"
			/>
			<input
				v-model.number="row.replacement_cost"
				class="input tabular"
				type="number"
				min="0"
				placeholder="Cost"
				title="Replacement cost of one"
			/>
			<button
				type="button"
				class="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-rose-600"
				title="Remove"
				@click="items.splice(i, 1)"
			>
				<Trash2 class="size-4" />
			</button>
		</div>
		<div class="flex flex-wrap items-center gap-1.5 pt-1">
			<button
				v-for="s in missing"
				:key="s.item"
				type="button"
				class="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-brand-50 hover:text-brand-700"
				@click="
					items.push({ item: s.item, quantity: 1, replacement_cost: s.replacement_cost })
				"
			>
				+ {{ s.item }}
			</button>
			<button
				type="button"
				class="text-xs font-medium text-brand-600 hover:underline"
				@click="items.push({ item: '', quantity: 1, replacement_cost: '' })"
			>
				+ Other item
			</button>
		</div>
	</div>
</template>

<script setup>
import { Trash2 } from "lucide-vue-next";
import { computed } from "vue";

// items: [{ item, quantity, replacement_cost }], edited in place
const props = defineProps({
	items: { type: Array, required: true },
	suggestions: { type: Array, default: () => [] },
});
const missing = computed(() => {
	const have = new Set(props.items.map((r) => (r.item || "").toLowerCase()));
	return props.suggestions.filter((s) => !have.has(s.item.toLowerCase()));
});
</script>
