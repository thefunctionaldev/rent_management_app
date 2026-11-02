<template>
	<Modal open :title="$t(title)" @close="$emit('close')">
		<form class="space-y-4" @submit.prevent="submit">
			<p v-if="hint" class="text-sm text-slate-500">{{ $t(hint) }}</p>
			<label v-for="f in fields" :key="f.key" class="block">
				<span class="label"
					>{{ $t(f.label || label(f.key)) }}{{ f.required ? " *" : "" }}</span
				>
				<select
					v-if="f.options"
					v-model="form[f.key]"
					class="input"
					:required="f.required"
					:disabled="f.disabled"
				>
					<option value="">—</option>
					<option v-for="o in f.options" :key="o.value ?? o" :value="o.value ?? o">
						{{ typeof o === 'object' ? o.label : $t(o) }}
					</option>
				</select>
				<textarea
					v-else-if="f.type === 'textarea'"
					v-model="form[f.key]"
					class="input"
					rows="3"
					:required="f.required"
				/>
				<input
					v-else-if="f.type === 'checkbox'"
					v-model="form[f.key]"
					type="checkbox"
					:true-value="1"
					:false-value="0"
				/>
				<input
					v-else
					v-model="form[f.key]"
					:type="f.type || 'text'"
					class="input"
					:required="f.required"
					:min="f.min"
					:max="f.max"
					:step="f.type === 'number' ? '0.01' : undefined"
					:disabled="f.disabled"
				/>
			</label>
			<p v-if="error" role="alert" class="text-sm text-rose-600">{{ error }}</p>
			<div class="flex justify-end gap-2">
				<Button @click="$emit('close')">{{ $t("Cancel") }}</Button
				><Button type="submit" variant="primary" :loading="busy">{{ $t("Save") }}</Button>
			</div>
		</form>
	</Modal>
</template>
<script setup>
import { reactive, ref } from "vue";
import Modal from "@/components/Modal.vue";
import Button from "@/components/Button.vue";
import { title as label } from "./shared";
const props = defineProps({
	title: String,
	hint: String,
	fields: Array,
	initial: Object,
	save: Function,
});
const emit = defineEmits(["close", "saved"]);
const form = reactive({ ...props.initial });
const busy = ref(false),
	error = ref("");
async function submit() {
	busy.value = true;
	error.value = "";
	try {
		const result = await props.save({ ...form });
		emit("saved", result);
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
</script>
