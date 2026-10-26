<template>
	<div class="space-y-4">
		<div class="card p-5">
			<h1 class="text-lg font-semibold">Requests</h1>
			<p class="text-sm text-slate-500">
				Repairs, cleaning, WiFi... your landlord gets it right away.
			</p>
			<form class="mt-4 space-y-3" @submit.prevent="submit">
				<Field label="What's the problem?" required>
					<input
						v-model="form.subject"
						class="input"
						required
						maxlength="140"
						placeholder="Fan not working"
					/>
				</Field>
				<div class="grid grid-cols-2 gap-3">
					<Field label="Type">
						<select v-model="form.category" class="input">
							<option v-for="c in categories" :key="c">{{ c }}</option>
						</select>
					</Field>
					<Field label="How urgent?">
						<select v-model="form.priority" class="input">
							<option>Low</option>
							<option>Medium</option>
							<option>High</option>
						</select>
					</Field>
				</div>
				<Field label="Details">
					<textarea v-model="form.description" class="input" rows="3" />
				</Field>
				<Button type="submit" variant="primary" class="w-full" :loading="saving"
					>Send request</Button
				>
			</form>
		</div>

		<div v-if="data && data.length" class="card">
			<h2 class="px-5 pt-4 font-semibold">Your requests</h2>
			<ul class="mt-2 divide-y divide-slate-100">
				<li v-for="r in data" :key="r.name" class="px-5 py-3.5">
					<div class="flex items-start justify-between gap-3">
						<div class="min-w-0">
							<p class="font-medium">{{ r.subject }}</p>
							<p class="text-xs text-slate-500">
								{{ r.category }} · {{ date(r.creation.slice(0, 10)) }}
							</p>
						</div>
						<StatusBadge :status="r.status" />
					</div>
					<p
						v-if="r.resolution"
						class="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600"
					>
						{{ r.resolution }}
					</p>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { reactive, ref } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { toast } from "@/store";
import { useResource } from "@/useResource";
import { date } from "@/utils";

import { call } from "../store";

const categories = [
	"Electrical",
	"Plumbing",
	"Furniture",
	"Cleaning",
	"Internet / WiFi",
	"Food",
	"Security",
	"Noise",
	"Other",
];
const { data, reload } = useResource(() => get(call("get_requests")), { initial: [] });
const form = reactive({
	subject: "",
	category: "Electrical",
	priority: "Medium",
	description: "",
});
const saving = ref(false);

async function submit() {
	saving.value = true;
	try {
		await post(call("create_request"), { ...form });
		toast("Request sent");
		Object.assign(form, { subject: "", description: "", priority: "Medium" });
		reload();
	} catch (e) {
		toast(e.message, "error");
	} finally {
		saving.value = false;
	}
}
</script>
