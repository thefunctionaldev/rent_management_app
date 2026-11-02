<template>
	<label class="flex items-center gap-2 text-sm"
		><span>Language / भाषा</span
		><select
			:value="language"
			:disabled="busy"
			class="rounded-lg border border-slate-200 bg-white p-2"
			aria-label="Language / भाषा"
			@change="change"
		>
			<option value="en">English</option>
			<option value="hi">हिन्दी</option></select
		><span v-if="error" role="alert" class="text-xs text-rose-600">{{ error }}</span></label
	>
</template>
<script setup>
import { ref } from "vue";
import { language, setLanguage } from "@/i18n";
const busy = ref(false),
	error = ref("");
async function change(e) {
	busy.value = true;
	error.value = "";
	try {
		await setLanguage(e.target.value);
	} catch (err) {
		error.value = err.message;
		e.target.value = language.value;
	} finally {
		busy.value = false;
	}
}
</script>
