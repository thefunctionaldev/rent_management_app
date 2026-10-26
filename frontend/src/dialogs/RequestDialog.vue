<template>
	<Modal
		open
		:title="request ? request.subject : 'New request'"
		:subtitle="
			request
				? `${request.tenant_name} · room ${request.room || '—'} · ${request.category}`
				: 'On behalf of a tenant'
		"
		@close="$emit('close')"
	>
		<form id="request-form" class="space-y-4" @submit.prevent="save">
			<template v-if="!request">
				<Field label="Tenant" required>
					<select v-model="form.tenant" class="input" required>
						<option value="" disabled>Select a tenant</option>
						<option v-for="t in tenants.data.value" :key="t.name" :value="t.name">
							{{ t.full_name }}{{ t.room ? ` · room ${t.room}` : "" }}
						</option>
					</select>
				</Field>
				<Field label="Subject" required>
					<input v-model="form.subject" class="input" required maxlength="140" />
				</Field>
				<div class="grid gap-4 sm:grid-cols-2">
					<Field label="Category">
						<select v-model="form.category" class="input">
							<option v-for="c in categories" :key="c">{{ c }}</option>
						</select>
					</Field>
					<Field label="Priority">
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
			</template>
			<template v-else>
				<p
					v-if="request.description"
					class="rounded-xl bg-slate-50 p-3 text-sm text-slate-700"
				>
					{{ request.description }}
				</p>
				<div class="grid gap-4 sm:grid-cols-2">
					<Field label="Status">
						<select v-model="form.status" class="input">
							<option>Open</option>
							<option>In Progress</option>
							<option>Resolved</option>
							<option>Closed</option>
						</select>
					</Field>
					<Field label="Priority">
						<select v-model="form.priority" class="input">
							<option>Low</option>
							<option>Medium</option>
							<option>High</option>
						</select>
					</Field>
				</div>
				<Field
					label="Reply to tenant"
					:hint="
						request.raised_via === 'Tenant App'
							? 'The tenant is told when the status changes'
							: ''
					"
				>
					<textarea
						v-model="form.resolution"
						class="input"
						rows="3"
						placeholder="Electrician coming tomorrow at 10"
					/>
				</Field>
			</template>
		</form>
		<template #footer>
			<Button @click="$emit('close')">Cancel</Button>
			<Button variant="primary" type="submit" form="request-form" :loading="loading">{{
				request ? "Save" : "Add request"
			}}</Button>
		</template>
	</Modal>
</template>

<script setup>
import { reactive } from "vue";

import { get, post } from "@/api";
import Button from "@/components/Button.vue";
import Field from "@/components/Field.vue";
import Modal from "@/components/Modal.vue";
import { useAction, useResource } from "@/useResource";

const props = defineProps({ request: { type: Object, default: null } });
const emit = defineEmits(["close"]);
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
const tenants = useResource(
	() => (props.request ? Promise.resolve([]) : get("get_tenants", { status: "Active" })),
	{
		initial: [],
	}
);

const r = props.request || {};
const form = reactive({
	tenant: "",
	subject: "",
	category: "Electrical",
	description: "",
	priority: r.priority || "Medium",
	status: r.status || "Open",
	resolution: r.resolution || "",
});

const { loading, run } = useAction(
	() =>
		post("save_request", {
			data: props.request ? { name: props.request.name, ...form } : form,
		}),
	{ success: props.request ? "Request updated" : "Request added" }
);
async function save() {
	await run();
	emit("close");
}
</script>
