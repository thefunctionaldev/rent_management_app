<template>
	<div class="space-y-6">
		<header>
			<h1 class="text-3xl font-semibold">{{ $t("Owner access") }}</h1>
			<p class="mt-2 text-slate-500">
				{{ $t("Owners see only properties explicitly assigned to their login.") }}
			</p>
			<a href="/owners" class="mt-2 inline-block text-brand-600 underline">{{
				$t("Open owner portal")
			}}</a>
		</header>
		<p v-if="error" role="alert" class="text-rose-600">{{ error }}</p>
		<div class="flex gap-2">
			<Button variant="primary" @click="grant()">{{ $t("Assign property") }}</Button
			><Button @click="document">{{ $t("Share document") }}</Button>
		</div>
		<p class="text-sm text-slate-500">
			{{
				$t(
					"Create an enabled User account first. Assigning a property does not send an invitation."
				)
			}}
		</p>
		<article
			v-for="r in grants"
			:key="r.name"
			class="card flex items-center justify-between gap-3 p-5"
		>
			<div>
				<p class="font-semibold">{{ r.user }}</p>
				<p class="text-sm text-slate-500">
					{{ r.property }} · {{ $t(r.active ? "Active" : "Revoked") }}
				</p>
			</div>
			<Button @click="grant(r)">{{ $t("Edit access") }}</Button>
		</article>
		<EditForm
			v-if="dialog"
			:key="dialog.id"
			v-bind="dialog"
			@close="dialog = null"
			@saved="saved"
		/>
		<section v-if="pendingDocument" class="card p-5">
			<p class="mb-3">
				{{ $t("Upload the document to finish sharing (PDF or image, up to 5 MB).") }}
			</p>
			<input
				type="file"
				accept="application/pdf,image/png,image/jpeg,image/webp"
				:disabled="busy"
				@change="attach"
			/>
		</section>
		<p v-if="notice" role="status">{{ $t(notice) }}</p>
	</div>
</template>
<script setup>
import { ref, onMounted } from "vue";
import Button from "@/components/Button.vue";
import EditForm from "./EditForm.vue";
import { read, write, upload } from "./shared";
const grants = ref([]),
	opts = ref({}),
	dialog = ref(null),
	error = ref(""),
	pendingDocument = ref(""),
	busy = ref(false),
	notice = ref("");
async function load() {
	try {
		[grants.value, opts.value] = await Promise.all([
			read("owners.grants"),
			read("catalog.options", { key: "owners" }),
		]);
	} catch (e) {
		error.value = e.message;
	}
}
const properties = () => ({
	key: "property",
	required: true,
	options: (opts.value.properties || []).map((p) => ({
		value: p.name,
		label: p.property_name || p.name,
	})),
});
function grant(row = {}) {
	dialog.value = {
		id: Date.now(),
		title: "Assign property",
		fields: [
			{
				key: "user",
				required: true,
				disabled: !!row.name,
				options: (opts.value.users || []).map((u) => ({ value: u.name, label: u.name })),
			},
			{ ...properties(), disabled: !!row.name },
			{ key: "active", type: "checkbox" },
		],
		initial: { active: 1, ...row },
		save: (values) => write("owners.grant", values),
	};
}
function document() {
	dialog.value = {
		id: Date.now(),
		title: "Share document",
		fields: [
			properties(),
			{ key: "title", required: true },
			{ key: "description", type: "textarea" },
		],
		initial: {},
		save: async (values) => {
			pendingDocument.value = await write("owners.add_document", values);
		},
	};
}
async function saved() {
	dialog.value = null;
	await load();
}
async function attach(e) {
	busy.value = true;
	error.value = "";
	try {
		await upload("Rent Owner Document", pendingDocument.value, "file", e.target.files[0]);
		pendingDocument.value = "";
		notice.value = "Document shared";
	} catch (err) {
		error.value = err.message;
	} finally {
		busy.value = false;
	}
}
onMounted(load);
</script>
