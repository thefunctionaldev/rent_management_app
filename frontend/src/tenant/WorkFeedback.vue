<template>
	<section v-if="orders.length || error" class="card space-y-4 p-5">
		<h2 class="font-semibold">{{ $t("Completed repairs") }}</h2>
		<p v-if="error" role="alert" class="text-rose-600">{{ error }}</p>
		<article v-for="r in orders" :key="r.name" class="space-y-2 border-t border-slate-100 pt-3">
			<p class="font-medium">{{ r.subject }}</p>
			<p class="text-sm text-slate-500">{{ r.completion_note }}</p>
			<a
				v-if="r.after_photo"
				:href="download('Rent Work Order', r.name, 'after_photo')"
				class="block text-sm text-brand-600 underline"
				>{{ $t("View completion photo") }}</a
			><Button v-if="r.status === 'Completed'" :disabled="busy" @click="confirm(r)">{{
				$t("Confirm repair completed")
			}}</Button>
			<p v-else class="text-sm">{{ $t("Confirmed") }}</p>
		</article>
	</section>
</template>
<script setup>
import { ref, onMounted } from "vue";
import Button from "@/components/Button.vue";
import { read, write, download } from "@/pages/suite/shared";
const orders = ref([]),
	busy = ref(false),
	error = ref("");
async function load() {
	try {
		orders.value = await read("workorders.tenant_orders");
	} catch (e) {
		error.value = e.message;
	}
}
async function confirm(r) {
	busy.value = true;
	error.value = "";
	try {
		await write("workorders.confirm", { name: r.name });
		await load();
	} catch (e) {
		error.value = e.message;
	} finally {
		busy.value = false;
	}
}
onMounted(load);
</script>
