<template>
	<Field :label="label" :hint="saved ? 'Saved. Leave blank to keep it.' : ''">
		<input
			:value="modelValue"
			type="password"
			class="input"
			autocomplete="new-password"
			:placeholder="saved ? '••••••••••' : ''"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
	</Field>
</template>

<script setup>
import Field from "@/components/Field.vue";

defineProps({
	modelValue: { type: String, default: "" },
	label: { type: String, required: true },
	saved: Boolean,
});
defineEmits(["update:modelValue"]);
</script>
