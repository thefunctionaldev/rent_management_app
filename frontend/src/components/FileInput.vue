<template>
	<label
		class="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-slate-300 px-4 py-3 text-sm hover:bg-slate-50"
	>
		<span
			class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-lg bg-slate-100 text-slate-500"
		>
			<img v-if="preview" :src="preview" alt="" class="size-full object-cover" />
			<FileText v-else-if="isPdf" class="size-5" />
			<Upload v-else class="size-5" />
		</span>
		<span class="min-w-0 flex-1">
			<span class="block truncate font-medium text-slate-700">{{ label }}</span>
			<span class="block text-xs text-slate-500">{{ hint }}</span>
		</span>
		<input type="file" accept="image/*,application/pdf" class="sr-only" @change="choose" />
	</label>
</template>

<script setup>
import { FileText, Upload } from "lucide-vue-next";
import { computed, ref } from "vue";

import { toast } from "@/store";
import { shrinkImage } from "@/utils";

// v-model: a data URL of the chosen photo (made smaller) or PDF; "" when nothing new is chosen
const props = defineProps({
	modelValue: { type: String, default: "" },
	current: { type: String, default: "" }, // the file already saved, if any
	placeholder: { type: String, default: "Add a photo or a PDF" },
});
const emit = defineEmits(["update:modelValue"]);

const name = ref("");
const isPdf = computed(() =>
	props.modelValue
		? props.modelValue.startsWith("data:application/pdf")
		: props.current.toLowerCase().endsWith(".pdf")
);
const preview = computed(() =>
	props.modelValue?.startsWith("data:image")
		? props.modelValue
		: props.current && !isPdf.value
		? props.current
		: ""
);
const label = computed(
	() => name.value || (props.current ? "Saved · tap to replace" : props.placeholder)
);
const hint = computed(() => (name.value ? "Ready to save" : "JPEG, PNG or PDF, up to 5 MB"));

function readAsDataUrl(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result);
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}

async function choose(event) {
	const file = event.target.files?.[0];
	event.target.value = "";
	if (!file) return;
	try {
		if (file.type === "application/pdf") {
			if (file.size > 5 * 1024 * 1024)
				return toast("That PDF is too large (5 MB at most)", "error");
			emit("update:modelValue", await readAsDataUrl(file));
		} else {
			emit("update:modelValue", await shrinkImage(file, 1800));
		}
		name.value = file.name;
	} catch {
		toast("That file could not be read", "error");
	}
}
</script>
