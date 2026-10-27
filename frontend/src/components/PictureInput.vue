<template>
	<div class="flex items-center gap-4">
		<div
			v-if="!buttonsOnly"
			class="relative shrink-0 overflow-hidden bg-slate-100"
			:class="round ? 'size-16 rounded-full' : 'h-20 w-32 rounded-xl'"
		>
			<img v-if="preview" :src="preview" :alt="name" class="size-full object-cover" />
			<Avatar v-else-if="round" :name="name || '?'" size="xl" />
			<span v-else class="grid size-full place-items-center text-slate-400">
				<ImageIcon class="size-6" />
			</span>
		</div>
		<div class="space-y-1.5">
			<div class="flex flex-wrap gap-2">
				<label
					class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
				>
					<Camera class="size-4" />
					{{ preview ? "Change photo" : "Add photo" }}
					<input
						type="file"
						accept="image/jpeg,image/png,image/webp"
						class="sr-only"
						@change="choose"
					/>
				</label>
				<button
					v-if="preview"
					type="button"
					class="rounded-lg px-2.5 py-1.5 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-rose-600"
					@click="$emit('update:modelValue', '')"
				>
					Remove
				</button>
			</div>
			<p v-if="error" class="text-xs text-rose-600">{{ error }}</p>
			<p v-else class="text-xs text-slate-500">JPEG, PNG or WebP</p>
		</div>
	</div>
</template>

<script setup>
import { Camera, Image as ImageIcon } from "lucide-vue-next";
import { computed, ref } from "vue";

import Avatar from "@/components/Avatar.vue";

// modelValue: the saved photo's URL, a new photo as a data URL, or "" for no photo
const props = defineProps({
	modelValue: { type: String, default: "" },
	name: { type: String, default: "" },
	round: { type: Boolean, default: false },
	buttonsOnly: { type: Boolean, default: false }, // the photo is already shown nearby
});
const emit = defineEmits(["update:modelValue"]);
const error = ref("");
const preview = computed(() => props.modelValue || "");

// photos from phone cameras are several MB: shrink them before they are sent
async function choose(event) {
	const file = event.target.files?.[0];
	event.target.value = "";
	if (!file) return;
	error.value = "";
	if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
		error.value = "Please choose a JPEG, PNG or WebP picture.";
		return;
	}
	try {
		emit("update:modelValue", await shrink(file, props.round ? 480 : 1280));
	} catch {
		error.value = "That picture could not be read. Please try another.";
	}
}

async function shrink(file, maxSize) {
	const bitmap = await createImageBitmap(file);
	const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
	const canvas = document.createElement("canvas");
	canvas.width = Math.round(bitmap.width * scale);
	canvas.height = Math.round(bitmap.height * scale);
	canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
	bitmap.close?.();
	return canvas.toDataURL("image/jpeg", 0.85);
}
</script>
