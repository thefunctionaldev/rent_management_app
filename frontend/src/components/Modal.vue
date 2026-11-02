<template>
	<Teleport to="body">
		<Transition
			enter-active-class="duration-200 ease-out"
			enter-from-class="opacity-0"
			leave-active-class="duration-150 ease-in"
			leave-to-class="opacity-0"
		>
			<div
				v-if="open"
				class="fixed inset-0 z-40 flex items-end justify-center bg-slate-900/25 p-0 backdrop-blur-md sm:items-center sm:p-6"
				@mousedown.self="close"
			>
				<div
					class="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl shadow-slate-900/20 sm:rounded-3xl"
					:class="widths[width]"
					role="dialog"
					aria-modal="true"
				>
					<div
						class="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4"
					>
						<div>
							<h2 class="text-base font-semibold text-slate-900">{{ $t(title) }}</h2>
							<p v-if="subtitle" class="mt-0.5 text-sm text-slate-500">
								{{ $t(subtitle) }}
							</p>
						</div>
						<button
							class="-mr-2 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
							aria-label="Close"
							@click="close"
						>
							<X class="size-5" />
						</button>
					</div>
					<div class="overflow-y-auto px-6 py-5">
						<slot />
					</div>
					<div
						v-if="$slots.footer"
						class="flex flex-col-reverse gap-2 border-t border-slate-100 bg-slate-50/60 px-6 py-3.5 sm:flex-row sm:justify-end"
					>
						<slot name="footer" />
					</div>
				</div>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { X } from "lucide-vue-next";
import { onBeforeUnmount, onMounted } from "vue";

const props = defineProps({
	open: Boolean,
	title: { type: String, default: "" },
	subtitle: { type: String, default: "" },
	width: { type: String, default: "md" },
});
const emit = defineEmits(["close"]);
const widths = { sm: "sm:max-w-md", md: "sm:max-w-lg", lg: "sm:max-w-2xl" };

const close = () => emit("close");
const onKey = (e) => props.open && e.key === "Escape" && close();
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>
